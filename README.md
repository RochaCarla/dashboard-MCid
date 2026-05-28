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

```json
{
  "meta": { "titulo": "...", "subtitulo": "...", "atualizado_em": "YYYY-MM-DD" },
  "linhas": [
    {
      "id": 1,
      "nome": "Linha de Atuação",
      "objetivo": "...",
      "atores": "...",
      "meta": "...",
      "acoes": [
        {
          "id": 101,
          "desc": "Descrição",
          "resp": "Responsável",
          "status": "em_andamento",
          "prioridade": "alta",
          "progresso": 30,
          "prazo": "2025-12-31",
          "notas": ""
        }
      ]
    }
  ]
}
```

**Status válidos:** `nao_iniciado` | `em_andamento` | `concluido` | `bloqueado` | `em_risco`

**Prioridades válidas:** `alta` | `media` | `baixa`

## Tecnologias
- **D3.js v7** — gráfico donut e barras de progresso
- **HTML/CSS puro** — sem frameworks
- **GitHub Actions** — CI/CD para sincronização
- **GitHub Pages** — hospedagem gratuita

## Adaptando para outro GT
1. Ajuste `COL_*` em `scripts/xlsx_to_json.py` para as colunas da sua planilha
2. Atualize `LINHA_META` com os metadados das suas linhas de atuação
3. Regenere o JSON e faça push
