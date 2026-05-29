# Skill: Dashboard GitHub Pages — Gestão de Ações GT

## Quando usar esta skill
Invoke when the user wants to **generate or update a GitHub Pages BI dashboard** from a spreadsheet (Excel/CSV/ODS) or a document (ODT) that tracks action lines ("linhas de atuação") with fields like Linha, Ação, Responsável, Status, Prioridade, Progresso, Prazo.

Trigger phrases (PT): "gerar dashboard", "atualizar painel", "criar gitpage", "novo dashboard da planilha", "dashboard das ações", "dashboard do odt", "importar documento"

---

## O que esta skill entrega
1. `index.html` — Dashboard D3.js completo (KPIs, donut chart, bar chart, tabela expansível com filtros)
2. `data/acoes.json` — Dados estruturados extraídos da planilha ou documento
3. `scripts/xlsx_to_json.py` — Conversor Python reutilizável (XLSX, CSV, ODS, ODT)
4. `.github/workflows/sync-sharepoint.yml` — GitHub Actions para sincronização automática
5. `README.md` — Guia de setup (GitHub Pages + SharePoint opcional)

---

## Protocolo de execução

### PASSO 1 — Coletar informações
Antes de gerar qualquer arquivo, pergunte (use AskUserQuestion):
- **Fonte dos dados**: Arquivo local (.xlsx/.csv/.ods/.odt) ou URL SharePoint/Google Sheets?
- **Nome do projeto**: Título do dashboard (ex: "GT Industrialização")
- **Subtítulo**: Organização / secretaria
- **Estrutura da planilha**: O usuário deve fornecer o arquivo OU descrever as colunas

### PASSO 2 — Analisar a fonte de dados

O conversor `xlsx_to_json.py` (v3) aceita 4 formatos:

| Formato | Extensão | Dependência | Notas |
|---------|----------|-------------|-------|
| Excel | .xlsx/.xls | openpyxl | Padrão corporativo |
| CSV | .csv | nenhuma | Auto-detect delimitador (`,` ou `;`) e encoding |
| ODS | .ods | nenhuma | OpenDocument Spreadsheet (LibreOffice) |
| ODT | .odt | nenhuma | OpenDocument Text — extrai a maior tabela embutida |

**Para ODT**: o conversor abre o ZIP, parseia `content.xml`, encontra a maior `<table:table>` e extrai as linhas como se fosse planilha.

```python
# Identifica automaticamente:
# - Formato pelo sufixo do arquivo
# - Índice de cada coluna (layout 8 ou 9 colunas)
# - Delimitador CSV (; ou ,) via csv.Sniffer
# - Valores únicos de Status e Prioridade (para normalização)
# - Número de eixos temáticos
```

Se for CSV com encoding problemático:
```bash
python3 -c "
import chardet
with open('arquivo.csv','rb') as f:
    print(chardet.detect(f.read()))
"
```

### PASSO 3 — Gerar acoes.json
Execute o conversor adaptando COL_* para as colunas detectadas:
```bash
python scripts/xlsx_to_json.py --file "Ações.xlsx" --out data/acoes.json
# Também aceita: .csv, .ods, .odt
python scripts/xlsx_to_json.py --file "documento.odt" --out data/acoes.json
```

Se o arquivo tiver encoding não-UTF-8:
```python
# Em xlsx_to_json.py, adicionar ao parse_excel():
wb = openpyxl.load_workbook(path, data_only=True)
# openpyxl lida com encoding automaticamente para .xlsx
# Para .csv: open(path, encoding='latin-1') ou 'cp1252'
```

**Estrutura JSON esperada:**
```json
{
  "meta": {
    "titulo": "...",
    "subtitulo": "...",
    "atualizado_em": "YYYY-MM-DD"
  },
  "linhas": [
    {
      "id": 1,
      "nome": "Nome da linha",
      "objetivo": "...",
      "atores": "...",
      "meta": "...",
      "acoes": [
        {
          "id": 101,
          "desc": "Descrição da ação",
          "resp": "Responsável",
          "status": "em_andamento",
          "prioridade": "alta",
          "progresso": 30,
          "prazo": "YYYY-MM-DD",
          "notas": ""
        }
      ]
    }
  ]
}
```

**Valores normalizados de status:**
- `nao_iniciado` | `em_andamento` | `concluido` | `bloqueado` | `em_risco`

**Valores normalizados de prioridade:**
- `alta` | `media` | `baixa`

### PASSO 4 — Adaptar index.html
O `index.html` base está em `dashboard-gt/index.html`. Customize:
1. **Cores** — variáveis CSS em `:root` (--navy, --teal, --gold)
2. **Título/subtítulo** — lidos do JSON automaticamente
3. **Colunas da tabela** — se houver campos extras, adicionar `<th>` e `<td>` no renderLinhas()
4. **Metadados das linhas** — `LINHA_META` no conversor Python (objetivo, atores, meta por id)

### PASSO 5 — Configurar GitHub Pages
Instruções para o usuário:
```
1. Crie um repositório no GitHub (ex: dashboard-gt)
2. Copie todos os arquivos para ele
3. Vá em Settings → Pages → Source: "Deploy from branch" → main → / (root)
4. Acesse: https://SEU_USUARIO.github.io/dashboard-gt/
```

### PASSO 6 — Configurar sincronização automática (opcional)
Para atualização automática via SharePoint:
```
Pré-requisito: Azure AD App Registration com permissão Sites.Read.All
1. Registre um App no portal Azure (portal.azure.com)
2. Adicione os secrets no GitHub:
   - SHAREPOINT_FILE_URL: URL de compartilhamento do arquivo
   - AZURE_TENANT_ID: ID do tenant
   - AZURE_CLIENT_ID: Client ID do app
   - AZURE_CLIENT_SECRET: Client Secret
3. Descomente o bloco "Download do SharePoint" no workflow
4. O dashboard atualizará todo dia às 7h (Brasília) automaticamente
```

---

## Personalização avançada

### Adicionar novos campos ao JSON
Se a planilha tiver campo extra (ex: "Observações da reunião"):
```python
# Em parse_excel(), adicionar:
COL_OBS = 10  # índice da coluna
# ...
acoes.append({
    ...
    "obs_reuniao": normalize(str(raw_row[COL_OBS] or ""))
})
```

No `index.html`, adicionar ao renderLinhas():
```javascript
${a.obs_reuniao ? `<div class="note">📋 ${a.obs_reuniao}</div>` : ""}
```

### Adicionar novo gráfico D3.js
```javascript
// Após renderBars(), adicionar:
function renderTimeline() {
  // Gráfico de Gantt com d3.scaleBand() e d3.scaleTime()
  // ...
}
```

### Múltiplas planilhas / GTs
Para suportar múltiplos GTs no mesmo dashboard:
1. Gerar `data/acoes-gt1.json`, `data/acoes-gt2.json`
2. Adicionar seletor no header do HTML
3. Recarregar dados com `loadData(filename)`

---

## Arquivos de referência
- Template dashboard: `dashboard-gt/index.html`
- Conversor (v3): `dashboard-gt/scripts/xlsx_to_json.py` — aceita XLSX, CSV, ODS, ODT
- Workflow SharePoint: `dashboard-gt/.github/workflows/sync-sharepoint.yml`
- Workflow Google Sheets: `dashboard-gt/.github/workflows/sync-google-sheets.yml`
- Dados exemplo: `dashboard-gt/data/acoes.json`
- Spec viz engine: `dashboard-gt/docs/SPEC-VIZ-ENGINE.md`

## Verificação final
Antes de entregar:
- [ ] JSON válido (`python -m json.tool data/acoes.json`)
- [ ] Dashboard abre localmente (abrir index.html no browser)
- [ ] Todos os campos do CSV mapeados corretamente
- [ ] Gráficos D3.js renderizando (verificar console do browser)
- [ ] Filtros e busca funcionando
- [ ] Export CSV funcionando
