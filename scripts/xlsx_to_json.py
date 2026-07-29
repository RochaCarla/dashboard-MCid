"""
xlsx_to_json.py  —  v3
Converte planilhas de ações (XLSX, CSV, ODS ou ODT com tabela embutida)
para data/acoes.json usado pelo dashboard GitHub Pages.

Formatos suportados:
    .xlsx / .xls  — Excel (requer openpyxl)
    .csv          — CSV com auto-detect de delimitador e encoding
    .ods          — OpenDocument Spreadsheet (sem dependência externa)
    .odt          — OpenDocument Text com tabela embutida (sem dependência externa)

Uso local:
    python scripts/xlsx_to_json.py --file "Ações.xlsx"
    python scripts/xlsx_to_json.py --file "planilha.csv"
    python scripts/xlsx_to_json.py --file "documento.odt"

Uso no GitHub Actions (SharePoint):
    python scripts/xlsx_to_json.py \
        --sharepoint-url "$SHAREPOINT_FILE_URL" \
        --tenant "$TENANT_ID" \
        --client-id "$CLIENT_ID" \
        --client-secret "$CLIENT_SECRET"
"""

import argparse, csv, json, re, sys, zipfile
from collections import OrderedDict
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from xml.etree import ElementTree as ET

# ── dependências (openpyxl carregado sob demanda para .xlsx) ──────────────────
openpyxl = None

# ── mapeamento de colunas  (índice 0-based) ───────────────────────────────────
# Detecta colunas pelo NOME no cabeçalho (a planilha pode reordenar colunas).
# Se o cabeçalho não tiver nomes reconhecíveis, cai no layout posicional legado:
#   8 colunas: Prioridade | Prazo | Eixo | Processo | Atividade | Tarefa | Responsável | Status
#   9 colunas: Prioridade | Prazo(ignorar) | Eixo | Processo | Atividade | Tarefa | Responsável | Prazo | Status
def detect_columns(header_row):
    names = [norm(c).lower() for c in header_row]

    def find(*terms):
        for i, n in enumerate(names):
            if any(t in n for t in terms):
                return i
        return None

    eixo = find("eixo", "linha")
    if eixo is not None:
        # quando há duas colunas "Prazo" (legado), a última é o prazo da tarefa
        prazos = [i for i, n in enumerate(names) if "prazo" in n]
        return {"prioridade": find("prioridade"), "eixo": eixo,
                "processo": find("processo"), "atividade": find("atividade"),
                "cod": find("cod_task", "cod task", "código", "codigo", "cod"),
                "tarefa": find("tarefa"), "depende": find("depende", "dependência", "dependencia"),
                "resp": find("respons"),
                "prazo": prazos[-1] if prazos else None, "status": find("status")}

    ncols = len(header_row)
    if ncols <= 8:
        return {"prioridade": 0, "eixo": 2, "processo": 3, "cod": None,
                "atividade": 4, "tarefa": 5, "depende": None,
                "resp": 6, "prazo": 1, "status": 7}
    else:
        return {"prioridade": 0, "eixo": 2, "processo": 3, "cod": None,
                "atividade": 4, "tarefa": 5, "depende": None,
                "resp": 6, "prazo": 7, "status": 8}

# defaults (overridden by detect_columns)
COL_PRIORIDADE = 0
COL_EIXO       = 2
COL_PROCESSO   = 3
COL_ATIVIDADE  = 4
COL_COD        = None
COL_TAREFA     = 5
COL_DEPENDE    = None
COL_RESP       = 6
COL_PRAZO      = 7
COL_STATUS     = 8

# ── normalização ──────────────────────────────────────────────────────────────
STATUS_MAP = {
    "em andamento": "em_andamento",
    "andamento":    "em_andamento",
    "não iniciado": "nao_iniciado",
    "nao iniciado": "nao_iniciado",
    "não iniciada": "nao_iniciado",
    "nao iniciada": "nao_iniciado",
    "em aberto":    "nao_iniciado",
    "aberto":       "nao_iniciado",
    "concluído":    "concluido",
    "concluido":    "concluido",
    "cumprido":     "concluido",
    "bloqueado":    "bloqueado",
    "stand by":     "bloqueado",
    "standby":      "bloqueado",
    "em risco":     "em_risco",
    "risco":        "em_risco",
    "":             "nao_iniciado",
}
PRIO_MAP = {
    "alta":  "alta",
    "média": "media",
    "media": "media",
    "médio": "media",
    "medio": "media",
    "baixa": "baixa",
    "":      "media",
}

# siglas institucionais grafadas de forma inconsistente na planilha; normalizadas
# aqui para o dashboard não exibir "MCid" e "MCID" na mesma tela
SIGLAS = [(re.compile(r"\bmcid\b", re.IGNORECASE), "MCID")]

def norm(v) -> str:
    s = re.sub(r"\s+", " ", str(v or "").strip())
    for rx, sigla in SIGLAS:
        s = rx.sub(sigla, s)
    return s

def parse_status(raw: str) -> str:
    k = norm(raw).lower()
    for kk, vv in STATUS_MAP.items():
        if kk and kk in k:
            return vv
    return "nao_iniciado"

def parse_prio(raw: str) -> str:
    return PRIO_MAP.get(norm(raw).lower(), "media")

def parse_prazo(raw) -> str:
    if raw is None: return ""
    if isinstance(raw, datetime): return raw.strftime("%Y-%m-%d")
    s = norm(str(raw))
    if s.lower() in ("em aberto", "aberto", ""): return ""
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try: return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError: pass
    return s

def parse_cod(raw) -> str:
    """Normaliza o Cod_Task ('1.1.1', ' 6.3.2 ', '7,2,1' → '7.2.1')."""
    s = norm(raw).replace(",", ".")
    return s if re.fullmatch(r"[\d]+(\.[\d]+)*", s) else s

def parse_deps(raw) -> list:
    """Coluna 'Depende de' → lista de Cod_Task predecessores.
    Aceita múltiplos códigos separados por ; / + ou espaço ('1.1.1; 2.3.1')."""
    s = norm(raw)
    if not s or s.lower() in ("-", "n/a", "não se aplica", "nao se aplica"):
        return []
    partes = re.split(r"[;,/+]|\s+e\s+|\s+", s)
    deps, vistos = [], set()
    for p in partes:
        c = p.strip().strip(".,")
        if c and re.fullmatch(r"[\d]+(\.[\d]+)*", c) and c not in vistos:
            vistos.add(c)
            deps.append(c)
    return deps

def eixo_id(text: str):
    m = re.match(r"^(\d+)\.", text.strip())
    return int(m.group(1)) if m else None

def eixo_nome(text: str) -> str:
    return re.sub(r"^\d+\.\s*", "", text.strip())

def is_admin_row(text: str) -> bool:
    skip = ["encaminhamentos", "agendar", "produzir documento", "trazer a frente",
            "sem equivalência", "sem equivalencia"]
    return any(s in text.lower() for s in skip)

# ── leitura de linhas brutas ──────────────────────────────────────────────────
def rows_from_xlsx(path: Path):
    global openpyxl
    if openpyxl is None:
        try:
            import openpyxl as _openpyxl
            openpyxl = _openpyxl
        except ImportError:
            sys.exit("Instale openpyxl:  pip install openpyxl")
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active
    raw = list(ws.iter_rows(values_only=True))
    # detecta cabeçalho
    hdr = 0
    for i, row in enumerate(raw[:6]):
        if any("eixo" in str(c or "").lower() or "linha" in str(c or "").lower() for c in row):
            hdr = i; break
    header = list(raw[hdr]) if raw else []
    data = [list(r) for r in raw[hdr+1:]]
    return header, data

def rows_from_csv(path: Path):
    for enc in ("utf-8-sig", "latin-1", "cp1252", "utf-8"):
        try:
            text = path.read_text(encoding=enc)
            # auto-detecta delimitador (; ou ,)
            try:
                dialect = csv.Sniffer().sniff(text[:2000], delimiters=";,")
                delim = dialect.delimiter
            except csv.Error:
                delim = ";" if ";" in text[:500] else ","
            print(f"  Delimitador detectado: '{delim}'")
            reader = csv.reader(StringIO(text), delimiter=delim)
            all_rows = list(reader)
            header = all_rows[0] if all_rows else []
            data = [r for r in all_rows[1:]]
            return header, data
        except UnicodeDecodeError:
            continue
    sys.exit("Não foi possível decodificar o arquivo CSV.")

def rows_from_odt(path: Path):
    """Extrai tabelas de arquivos ODS (.ods) ou ODT (.odt) usando zipfile + xml.
    Ambos são arquivos ZIP contendo content.xml com tabelas ODF."""
    NS = {
        "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
        "text":  "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
        "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    }
    try:
        with zipfile.ZipFile(path) as zf:
            content = zf.read("content.xml")
    except (zipfile.BadZipFile, KeyError) as e:
        sys.exit(f"Arquivo ODT/ODS inválido: {e}")

    root = ET.fromstring(content)
    # Encontra todas as tabelas no documento
    tables = root.findall(".//table:table", NS)
    if not tables:
        sys.exit("Nenhuma tabela encontrada no documento ODT/ODS.")

    # Usa a maior tabela (mais linhas)
    best_table = max(tables, key=lambda t: len(t.findall("table:table-row", NS)))
    table_name = best_table.get(f"{{{NS['table']}}}name", "(sem nome)")
    print(f"  Tabela selecionada: '{table_name}'")

    all_rows = []
    for tr in best_table.findall("table:table-row", NS):
        # Respeita table:number-rows-repeated
        row_repeat = int(tr.get(f"{{{NS['table']}}}number-rows-repeated", "1"))
        cells = []
        for tc in tr.findall("table:table-cell", NS):
            col_repeat = int(tc.get(f"{{{NS['table']}}}number-columns-repeated", "1"))
            # Extrai texto de todos os <text:p> dentro da célula
            text_parts = []
            for p in tc.findall(".//text:p", NS):
                text_parts.append("".join(p.itertext()))
            cell_text = "\n".join(text_parts)
            cells.extend([cell_text] * col_repeat)
        # Ignora linhas completamente vazias no final
        if any(c.strip() for c in cells):
            for _ in range(min(row_repeat, 1)):  # só 1 cópia de linhas com conteúdo
                all_rows.append(cells)

    if not all_rows:
        sys.exit("Tabela encontrada mas sem dados.")

    # Detecta cabeçalho
    hdr = 0
    for i, row in enumerate(all_rows[:6]):
        if any("eixo" in str(c or "").lower() or "linha" in str(c or "").lower()
               or "prioridade" in str(c or "").lower() for c in row):
            hdr = i; break

    header = all_rows[hdr]
    data = all_rows[hdr+1:]
    print(f"  {len(data)} linhas de dados extraídas do ODT/ODS")
    return header, data

def read_file(path: Path):
    suf = path.suffix.lower()
    if suf in (".xlsx", ".xls"):
        return rows_from_xlsx(path)
    elif suf == ".csv":
        return rows_from_csv(path)
    elif suf in (".odt", ".ods"):
        return rows_from_odt(path)
    else:
        sys.exit(f"Formato não suportado: {suf}. Use .xlsx, .csv, .ods ou .odt")

def setup_columns(header):
    global COL_PRIORIDADE, COL_EIXO, COL_PROCESSO, COL_ATIVIDADE
    global COL_COD, COL_TAREFA, COL_DEPENDE, COL_RESP, COL_PRAZO, COL_STATUS
    cols = detect_columns(header)
    COL_PRIORIDADE = cols["prioridade"]
    COL_EIXO       = cols["eixo"]
    COL_PROCESSO   = cols["processo"]
    COL_ATIVIDADE  = cols["atividade"]
    COL_COD        = cols["cod"]
    COL_TAREFA     = cols["tarefa"]
    COL_DEPENDE    = cols["depende"]
    COL_RESP       = cols["resp"]
    COL_PRAZO      = cols["prazo"]
    COL_STATUS     = cols["status"]
    ncols = len(header)
    print(f"  Layout detectado: {ncols} colunas → Eixo na col {COL_EIXO}, Status na col {COL_STATUS}")
    print(f"  Cod_Task: {'col ' + str(COL_COD) if COL_COD is not None else 'ausente'}"
          f"  ·  Depende de: {'col ' + str(COL_DEPENDE) if COL_DEPENDE is not None else 'ausente'}")

# ── parse + agrupamento ───────────────────────────────────────────────────────
def parse_rows(raw_rows) -> list:
    def cell(row, idx, default=""):
        if idx is None: return default
        try: return norm(row[idx]) if row[idx] is not None else default
        except IndexError: return default

    # propaga contexto (células mescladas ficam vazias nas linhas seguintes),
    # respeitando a hierarquia: mudar de Eixo invalida Processo/Atividade
    # herdados; mudar de Processo invalida Atividade herdada.
    prev = {"eixo": "", "processo": "", "atividade": ""}
    records = []
    for row in raw_rows:
        r = {
            "prioridade": cell(row, COL_PRIORIDADE),
            "eixo":       cell(row, COL_EIXO),
            "processo":   cell(row, COL_PROCESSO),
            "atividade":  cell(row, COL_ATIVIDADE),
            "cod":        parse_cod(cell(row, COL_COD)),
            "tarefa":     cell(row, COL_TAREFA),
            "depende":    parse_deps(cell(row, COL_DEPENDE)),
            "resp":       cell(row, COL_RESP),
            "prazo":      cell(row, COL_PRAZO),
            "status":     cell(row, COL_STATUS),
        }
        if not r["eixo"]:
            r["eixo"] = prev["eixo"]
        elif r["eixo"] != prev["eixo"]:
            prev["processo"] = prev["atividade"] = ""

        if not r["processo"]:
            r["processo"] = prev["processo"]
        elif r["processo"] != prev["processo"]:
            prev["atividade"] = ""

        if not r["atividade"]:
            r["atividade"] = prev["atividade"]

        prev = {"eixo": r["eixo"], "processo": r["processo"],
                "atividade": r["atividade"]}

        if not r["eixo"] or is_admin_row(r["eixo"]):
            continue

        records.append(r)
    return records

def build_json(records: list) -> dict:
    eixos: dict[int, dict] = OrderedDict()
    counter = 0

    for r in records:
        eid = eixo_id(r["eixo"]) if r["eixo"] else None
        if not eid:
            continue

        if eid not in eixos:
            eixos[eid] = {
                "id":      eid,
                "nome":    eixo_nome(r["eixo"]),
                "objetivo": "",
                "atores":   "",
                "meta":     "",
                "processos": OrderedDict(),
            }

        # linha só com Eixo (sem processo/atividade/tarefa): registra o eixo,
        # mas não cria tarefa
        desc = r["tarefa"] or r["atividade"] or r["processo"]
        if not desc:
            continue

        # Quando a planilha tem Cod_Task, ele é a identidade da tarefa: linhas
        # sem código E sem Tarefa são continuações de célula mesclada (ex.: só
        # um prazo extra), não entregas — evita tarefas fantasma duplicadas.
        if COL_COD is not None and not r["cod"] and not r["tarefa"]:
            continue

        proc_key = r["processo"] or r["atividade"] or "Geral"
        if proc_key not in eixos[eid]["processos"]:
            eixos[eid]["processos"][proc_key] = []

        counter += 1
        status_norm = parse_status(r["status"])
        progresso = {"concluido": 100, "em_andamento": 50, "nao_iniciado": 0,
                     "bloqueado": 25, "em_risco": 25}.get(status_norm, 0)

        eixos[eid]["processos"][proc_key].append({
            "id":         int(f"{eid}{counter:03d}"),
            "cod":        r["cod"],
            "atividade":  r["atividade"],
            "desc":       desc,
            "resp":       r["resp"],
            "status":     status_norm,
            "prioridade": parse_prio(r["prioridade"]),
            "progresso":  progresso,
            "prazo":      parse_prazo(r["prazo"]),
            "depende_de": r["depende"],
            "notas":      "",
        })

    # serializa
    linhas_out = []
    for eid, e in eixos.items():
        processos_out = [
            {"processo": pnome, "tarefas": tarefas}
            for pnome, tarefas in e["processos"].items()
        ]
        linhas_out.append({
            "id":       e["id"],
            "nome":     e["nome"],
            "objetivo": e["objetivo"],
            "atores":   e["atores"],
            "meta":     e["meta"],
            "processos": processos_out,
        })
    return linhas_out

# ── validação do grafo de dependências ────────────────────────────────────────
def validar_dependencias(linhas) -> dict:
    """Confere o grafo Cod_Task → Depende de e devolve métricas.
    Remove referências que não resolvem (código inexistente) para que o
    front-end nunca desenhe uma aresta órfã."""
    todas = [t for l in linhas for p in l["processos"] for t in p["tarefas"]]
    por_cod: dict[str, list] = {}
    for t in todas:
        if t.get("cod"):
            por_cod.setdefault(t["cod"], []).append(t)

    for cod, ts in por_cod.items():
        if len(ts) > 1:
            print(f"  ⚠ Cod_Task duplicado na planilha: {cod} ({len(ts)}×)")

    orfas, vinculos = [], 0
    for t in todas:
        validas = []
        for d in t.get("depende_de", []):
            if d == t.get("cod"):
                print(f"  ⚠ {t['cod']} depende de si mesma — ignorado")
            elif d in por_cod:
                validas.append(d)
                vinculos += 1
            else:
                orfas.append((t.get("cod") or t["desc"][:30], d))
        t["depende_de"] = validas

    for origem, alvo in orfas:
        print(f"  ⚠ Dependência não encontrada: '{origem}' → '{alvo}' (código inexistente)")

    # detecção de ciclos (DFS com marcação de cor)
    sucessores: dict[str, list] = {}
    for t in todas:
        for d in t.get("depende_de", []):
            sucessores.setdefault(d, []).append(t.get("cod"))

    BRANCO, CINZA, PRETO = 0, 1, 2
    cor = {c: BRANCO for c in por_cod}
    ciclos = []

    def visitar(c, caminho):
        cor[c] = CINZA
        for s in sucessores.get(c, []):
            if s is None or s not in cor:
                continue
            if cor[s] == CINZA:
                ciclos.append(" → ".join(caminho[caminho.index(s):] + [s]))
            elif cor[s] == BRANCO:
                visitar(s, caminho + [s])
        cor[c] = PRETO

    for c in list(cor):
        if cor[c] == BRANCO:
            visitar(c, [c])
    for ciclo in ciclos:
        print(f"  ⚠ Ciclo de dependência detectado: {ciclo}")

    # bloqueadas por dependência: predecessor ainda não concluído
    bloqueadas = 0
    for t in todas:
        deps = t.get("depende_de", [])
        if not deps or t.get("status") == "concluido":
            continue
        if any(any(p.get("status") != "concluido" for p in por_cod[d]) for d in deps):
            bloqueadas += 1

    print(f"  Dependências: {vinculos} vínculos válidos, {bloqueadas} tarefas travadas, "
          f"{len(orfas)} referências órfãs removidas, {len(ciclos)} ciclos")
    return {"vinculos": vinculos, "bloqueadas": bloqueadas,
            "orfas": len(orfas), "ciclos": len(ciclos)}

# ── download SharePoint ───────────────────────────────────────────────────────
def download_sharepoint(url, tenant, client_id, secret, dest: Path):
    try: import requests
    except ImportError: sys.exit("pip install requests")
    tok = requests.post(
        f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
        data={"grant_type":"client_credentials","client_id":client_id,
              "client_secret":secret,"scope":"https://graph.microsoft.com/.default"},
        timeout=30).json()["access_token"]
    enc = "u!" + url.replace("https://","").replace("/","_").replace(".","_")
    r = requests.get(f"https://graph.microsoft.com/v1.0/shares/{enc}/root/content",
                     headers={"Authorization":f"Bearer {tok}"}, timeout=60)
    r.raise_for_status()
    dest.write_bytes(r.content)
    print(f"✓ Baixado → {dest}")
    return dest

# ── main ──────────────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--file")
    p.add_argument("--sharepoint-url")
    p.add_argument("--tenant")
    p.add_argument("--client-id")
    p.add_argument("--client-secret")
    p.add_argument("--out", default="data/acoes.json")
    p.add_argument("--titulo",    default="Painel de Gestão")
    p.add_argument("--subtitulo", default="Ministério das Cidades · Secretaria Nacional de Habitação")
    p.add_argument("--proxima-reuniao", default="",
                   help="data da próxima reunião do GT (YYYY-MM-DD); vazio oculta o campo")
    p.add_argument("--guardia", default="Equipe CEAG",
                   help="responsável pela manutenção da base")
    args = p.parse_args()

    if args.file:
        path = Path(args.file)
        if not path.exists(): sys.exit(f"Arquivo não encontrado: {path}")
    elif args.sharepoint_url:
        path = Path("/tmp/acoes_dl.xlsx")
        download_sharepoint(args.sharepoint_url, args.tenant,
                            args.client_id, args.client_secret, path)
    else:
        sys.exit("Forneça --file ou --sharepoint-url")

    print(f"Lendo {path} …")
    header, raw_rows = read_file(path)
    setup_columns(header)
    records  = parse_rows(raw_rows)
    linhas   = build_json(records)
    deps_info = validar_dependencias(linhas)

    total_tarefas = sum(len(p2["tarefas"]) for l in linhas for p2 in l["processos"])
    now = datetime.now(timezone.utc)
    data = {
        "meta": {
            "titulo":          args.titulo,
            "subtitulo":       args.subtitulo,
            "atualizado_em":   now.strftime("%Y-%m-%d"),
            "sincronizado_em": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "proxima_reuniao": args.proxima_reuniao,
            "guardia":         args.guardia,
            "schema":          "v2",
            "dependencias":    deps_info,
        },
        "linhas": linhas,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ {out}  →  {len(linhas)} eixos, {total_tarefas} tarefas")

    # série histórica
    hist_path = out.parent / "historico.json"
    append_snapshot(linhas, hist_path)

# ── série histórica ─────────────────────────────────────────────────────────
def append_snapshot(linhas, hist_path: Path):
    """Calcula métricas agregadas e adiciona ao histórico.
    Se já houver snapshot do mesmo dia, ele é substituído pelo estado atual."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # carrega histórico existente ou cria novo
    if hist_path.exists():
        historico = json.loads(hist_path.read_text(encoding="utf-8"))
    else:
        historico = {"snapshots": []}

    # substitui snapshot do mesmo dia (mantém o estado mais recente)
    historico["snapshots"] = [s for s in historico["snapshots"] if s["date"] != today]

    # coleta todas as tarefas
    todas = [t for l in linhas for p in l["processos"] for t in p["tarefas"]]
    total = len(todas)

    # contagem por status
    por_status = {}
    for t in todas:
        s = t.get("status", "nao_iniciado")
        por_status[s] = por_status.get(s, 0) + 1

    # progresso médio geral
    progresso_medio = round(sum(t.get("progresso", 0) for t in todas) / total, 1) if total else 0

    # progresso por eixo
    por_eixo = []
    for l in linhas:
        tarefas_eixo = [t for p in l["processos"] for t in p["tarefas"]]
        n = len(tarefas_eixo)
        prog = round(sum(t.get("progresso", 0) for t in tarefas_eixo) / n, 1) if n else 0
        status_eixo = {}
        for t in tarefas_eixo:
            s = t.get("status", "nao_iniciado")
            status_eixo[s] = status_eixo.get(s, 0) + 1
        por_eixo.append({
            "id": l["id"],
            "nome": l["nome"],
            "total": n,
            "progresso": prog,
            "status": status_eixo,
        })

    # dependências: quantas tarefas estão travadas esperando um predecessor
    por_cod = {t["cod"]: t for t in todas if t.get("cod")}
    travadas = sum(
        1 for t in todas
        if t.get("status") != "concluido" and t.get("depende_de")
        and any(por_cod.get(d, {}).get("status") != "concluido" for d in t["depende_de"])
    )

    snapshot = {
        "date": today,
        "total_tarefas": total,
        "total_eixos": len(linhas),
        "progresso_medio": progresso_medio,
        "por_status": por_status,
        "por_eixo": por_eixo,
        "travadas_por_dependencia": travadas,
    }

    historico["snapshots"].append(snapshot)
    historico["snapshots"].sort(key=lambda s: s["date"])
    hist_path.write_text(json.dumps(historico, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ {hist_path}  →  snapshot {today} adicionado ({len(historico['snapshots'])} total)")

if __name__ == "__main__":
    main()
