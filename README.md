# Dashboard GT — Painel de Gestão de Ações

Dashboard BI para GitHub Pages, gerado dinamicamente a partir da planilha **Ações.xlsx**.

## Estrutura do projeto

```
dashboard-gt/
├── index.html                          ← Dashboard (abrir no browser)
├── data/
│   └── acoes.json                      ← Dados gerados pelo conversor
├── scripts/
│   └── xlsx_to_json.py                 ← Conversor planilha → JSON
├── .github/
│   └── workflows/
│       └── sync-sharepoint.yml         ← Atualização automática
└── skill-dashboard-gt/
    └── SKILL.md                        ← Skill reutilizável (Cowork)
```

## Setup rápido (5 min)

### 1. Publicar no GitHub Pages
```bash
# Crie um repositório no GitHub e envie os arquivos
git init
git add .
git commit -m "Dashboard GT — versão inicial"
git remote add origin https://github.com/SEU_USUARIO/dashboard-gt.git
git push -u origin main
```

Vá em **Settings → Pages → Source: Deploy from branch → main → / (root)**

Seu painel estará em: `https://SEU_USUARIO.github.io/dashboard-gt/`

### 2. Atualizar dados manualmente
Sempre que a planilha mudar:
```bash
pip install openpyxl
python scripts/xlsx_to_json.py --file "Ações.xlsx"
git add data/acoes.json
git commit -m "Atualiza dados"
git push
```
O GitHub Pages publica automaticamente em ~1 min.

### 3. Atualização automática via SharePoint (opcional)
Requer Azure AD com permissão **Sites.Read.All**.

**Passo a passo:**
1. [portal.azure.com](https://portal.azure.com) → App registrations → New registration
2. Certificates & secrets → New client secret (guarde o valor)
3. API permissions → Add → Microsoft Graph → Application → `Sites.Read.All`
4. No GitHub: Settings → Secrets → Actions → adicionar:
   - `SHAREPOINT_FILE_URL` — URL de compartilhamento do arquivo
   - `AZURE_TENANT_ID`
   - `AZURE_CLIENT_ID`
   - `AZURE_CLIENT_SECRET`
5. Em `.github/workflows/sync-sharepoint.yml`, descomente o bloco **"Download do SharePoint"**

O dashboard passará a se atualizar **todo dia às 7h (Brasília)** automaticamente.

## Estrutura do JSON (`data/acoes.json`)

Formato **v2** (atual): Eixo Temático → Processos → Tarefas.

```json
{
  "meta": {
    "titulo": "...", "subtitulo": "...", "atualizado_em": "YYYY-MM-DD",
    "schema": "v2",
    "dependencias": { "vinculos": 16, "bloqueadas": 15, "orfas": 0, "ciclos": 0 }
  },
  "linhas": [
    {
      "id": 6,
      "nome": "Padronização do Código de Obras",
      "objetivo": "", "atores": "", "meta": "",
      "processos": [
        {
          "processo": "Aprovação da Minuta de Padronização do Código de Obras",
          "tarefas": [
            {
              "id": 6026,
              "cod": "6.3.2",
              "atividade": "Dialogar com a CAIXA sobre incentivos aos Municípios",
              "desc": "Realizar estudo de impacto",
              "resp": "Caixa",
              "status": "nao_iniciado",
              "prioridade": "alta",
              "progresso": 0,
              "prazo": "3 meses",
              "depende_de": ["6.3.1"],
              "notas": ""
            }
          ]
        }
      ]
    }
  ]
}
```

O schema **v1** (`linhas[].acoes[]`, sem Processo, sem `cod`/`depende_de`) continua suportado pelo front-end.

**Status válidos:** `nao_iniciado` | `em_andamento` | `concluido` | `bloqueado` | `em_risco`

**Prioridades válidas:** `alta` | `media` | `baixa`

**`cod` / `depende_de`:** vêm das colunas `Cod_Task` e `Depende de` da planilha. `depende_de` é a lista de códigos que precisam estar concluídos antes desta tarefa; o conversor descarta referências que não resolvem e avisa sobre ciclos e códigos duplicados. Quando a planilha não tem essas colunas, `cod` fica vazio, `depende_de` fica `[]` e a seção de dependências não aparece no dashboard.

## Rede de dependências

O dashboard monta um grafo dirigido a partir de `cod` → `depende_de` e oferece **duas visualizações** do mesmo grafo:

**🕸 Rede** — camadas da esquerda para a direita: cada coluna é um passo da cadeia, cada seta liga uma entrega ao seu pré-requisito (verde = cumprido, vermelha tracejada = ainda aberto). Mostra *o que vem antes do quê*.

**📅 Gantt** — as mesmas cadeias posicionadas no tempo, com marcador de "hoje" e setas de dependência ligando o fim de uma barra ao início da seguinte. Mostra *quando*.

Complementam a seção:

- **KPIs**: vínculos mapeados, entregas travadas, prontas para iniciar, cadeia mais longa e principal gargalo
- **Recortes** (valem para as duas visões): todas as cadeias · só com bloqueio · prontas para iniciar
- **Gargalos**: entregas em aberto que seguram outras, ordenadas pelo nº de entregas que destravam
- **Nas tabelas**: coluna `Cód.`, chips clicáveis de pré-requisito e selo 🔒 travada / 🚦 pronta

Passar o mouse sobre uma entrega realça a cadeia inteira; clicar leva à tarefa na tabela do eixo. Os filtros 🔒 e 🚦 da barra de filtros aplicam o mesmo recorte às tabelas.

### Datas do Gantt são derivadas

A planilha tem **um** prazo por tarefa, sem data de início. O Gantt calcula a janela por passagem para frente: o início é quando o último pré-requisito termina (nunca antes da data de sincronização) e o fim vem, nesta ordem, do prazo da planilha, da duração declarada ("3 meses") ou de uma estimativa de 30 dias. **Barras hachuradas são estimativas** e a nota sob o gráfico informa quantas entregas caem em cada caso. É ordenação de dependências no tempo, não CPM — não há duração real por tarefa nem caminho crítico calculado, e o gráfico não substitui o cronograma pactuado no GT.

## Tecnologias
- **D3.js v7** — donut, barras de progresso, série histórica e grafo de dependências
- **HTML/CSS puro** — sem frameworks
- **GitHub Actions** — CI/CD para sincronização
- **GitHub Pages** — hospedagem gratuita

## Adaptando para outro GT
1. Ajuste `COL_*` em `scripts/xlsx_to_json.py` para as colunas da sua planilha
2. Atualize `LINHA_META` com os metadados das suas linhas de atuação
3. Regenere o JSON e faça push
