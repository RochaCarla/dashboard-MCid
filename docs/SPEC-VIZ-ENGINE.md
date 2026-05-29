# Spec: Motor de Visualização Adaptativa

## Resumo

Motor embarcado no dashboard-gt que **analisa automaticamente os dados do JSON** e escolhe o tipo de gráfico mais adequado para cada dimensão, sem intervenção humana. Usa Observable Plot (wrapper declarativo sobre D3.js) para renderização.

---

## Arquitetura

```
CSV/XLSX/ODS/ODT → xlsx_to_json.py (v3) → acoes.json → [VIZ ENGINE] → Dashboard
      ↑                                                      ↓
  Google Sheets                                     1. Detecta tipos de coluna
  (export CSV)                                      2. Classifica dimensões
                                                    3. Seleciona visualização
                                                    4. Renderiza com Observable Plot
```

### Formatos de entrada suportados

| Formato | Extensão | Dependência | Como funciona |
|---------|----------|-------------|---------------|
| Excel | .xlsx/.xls | openpyxl | Leitura direta de células |
| CSV | .csv | nenhuma | Auto-detect delimitador (`,`/`;`) e encoding |
| ODS | .ods | nenhuma | ZIP → content.xml → tabelas ODF |
| ODT | .odt | nenhuma | ZIP → content.xml → extrai maior `<table:table>` |
| Google Sheets | URL | nenhuma (curl) | Export CSV via URL pública |

O motor roda **no frontend** (JavaScript), analisando o JSON em tempo de carga. Não requer backend.

---

## Detecção de tipos de dado

O motor infere o tipo de cada campo do JSON inspecionando os valores:

| Tipo inferido | Condição de detecção | Exemplos |
|---|---|---|
| `categorical_finite` | String com ≤ 7 valores únicos | status, prioridade |
| `categorical_open` | String com > 7 valores únicos | responsável, processo |
| `numeric_percent` | Número 0–100 OU campo com nome *progress/progresso* | progresso |
| `numeric_count` | Inteiro sem limite superior óbvio | contagem de tarefas |
| `numeric_currency` | Número + campo contém "orçamento/valor/custo/R$" | orçamento |
| `temporal_date` | String ISO date (YYYY-MM-DD) ou Date object | prazo |
| `temporal_duration` | Diferença entre duas datas | tempo restante |
| `hierarchical` | Campos aninhados (eixo → processo → tarefa) | estrutura do GT |
| `text` | String longa (>50 chars) sem padrão | descrição, notas |
| `boolean` | true/false ou binário | flag |

### Regras de inferência (pseudocódigo)

```javascript
function inferType(fieldName, values) {
  const nonEmpty = values.filter(v => v !== null && v !== "");
  if (!nonEmpty.length) return "text";

  // Temporal
  if (nonEmpty.every(v => /^\d{4}-\d{2}-\d{2}/.test(v))) return "temporal_date";

  // Numérico
  if (nonEmpty.every(v => typeof v === "number" || !isNaN(Number(v)))) {
    const nums = nonEmpty.map(Number);
    const max = Math.max(...nums);
    const min = Math.min(...nums);
    if (min >= 0 && max <= 100 && /progress|progresso/i.test(fieldName))
      return "numeric_percent";
    if (/orçamento|valor|custo|budget/i.test(fieldName))
      return "numeric_currency";
    if (Number.isInteger(max)) return "numeric_count";
    return "numeric_percent"; // fallback numérico
  }

  // Categórico
  const uniq = new Set(nonEmpty.map(v => String(v).toLowerCase()));
  if (uniq.size <= 7) return "categorical_finite";
  if (uniq.size <= 20) return "categorical_open";

  return "text";
}
```

---

## Mapeamento: Tipo de dado → Visualização

### Regras primárias (auto-seleção)

| Tipo de dado | Visualização | Condição extra | Lib call |
|---|---|---|---|
| `categorical_finite` | **Donut** | ≤ 5 categorias | `Plot.pie` + arc |
| `categorical_finite` | **Barras empilhadas** | 6–7 categorias | `Plot.barX` |
| `categorical_open` × `numeric_*` | **Barras horizontais** | > 7 itens | `Plot.barX` |
| `categorical_open` × `numeric_*` | **Barras verticais** | ≤ 7 itens | `Plot.barY` |
| `numeric_percent` por grupo | **Barra de progresso** | agrupado por eixo/processo | `Plot.barX` com domínio [0,100] |
| `numeric_currency` | **Barras ordenadas** | sempre decrescente | `Plot.barX` + sort |
| `numeric_currency` × `categorical` | **Treemap** | > 10 itens | `Plot.treemap` (ou d3.treemap fallback) |
| `temporal_date` | **Timeline / Gantt** | se houver par (início, fim) | `Plot.ruleX` + `Plot.dot` |
| `temporal_date` | **Linha do tempo** | contagem por mês | `Plot.lineY` + `Plot.areaY` |
| `numeric_count` (agregado) | **KPI card** | campos globais (total, média) | HTML puro |
| `hierarchical` | **Tabela expansível** | sempre | HTML (já existente) |
| `categorical_finite` × `temporal_date` | **Heatmap** | status ao longo do tempo | `Plot.cell` |

### Regras de composição

O motor gera um **layout de seções** automaticamente:

```
┌─────────────────────────────────────────────────────────┐
│  KPI Cards (sempre no topo — agregações numéricas)       │
├─────────────────┬───────────────────────────────────────┤
│  Donut/Pie      │  Barras principais                     │
│  (1 categórico  │  (progresso ou volume por grupo)       │
│   finito)       │                                        │
├─────────────────┴───────────────────────────────────────┤
│  Timeline / Gantt (se houver dados temporais)            │
├─────────────────────────────────────────────────────────┤
│  Gráficos secundários (novos campos detectados)          │
├─────────────────────────────────────────────────────────┤
│  Tabela detalhada (hierárquica, sempre por último)       │
└─────────────────────────────────────────────────────────┘
```

### Prioridade de exibição

1. **KPIs** — sempre presentes (contagem total, % concluído, bloqueados)
2. **Distribuição primária** — o primeiro campo `categorical_finite` vira donut
3. **Progresso por grupo** — `numeric_percent` agrupado pelo nível mais alto da hierarquia
4. **Temporais** — se existirem campos de data com dados reais (não "em aberto")
5. **Campos novos** — qualquer campo detectado que não encaixe nos anteriores ganha um gráfico secundário
6. **Tabela** — sempre por último, com todos os detalhes

---

## Tratamento de campos novos

Quando o JSON ganhar um campo que não existia antes (ex: planilha futura com "Orçamento"):

1. Motor detecta campos presentes em `tarefas[]` que não são do schema base
2. Infere tipo via `inferType()`
3. Gera card de visualização no bloco "Gráficos secundários"
4. Título do card = nome do campo capitalizado

**Schema base** (campos conhecidos que já têm visualização fixa):
```javascript
const KNOWN_FIELDS = [
  "id", "desc", "resp", "status", "prioridade",
  "progresso", "prazo", "notas", "atividade", "processo"
];
```

Qualquer campo em `tarefas[]` que **não** esteja nessa lista é tratado como campo dinâmico.

---

## Integração com Observable Plot

### Dependência

```html
<script type="module">
  import * as Plot from "https://cdn.jsdelivr.net/npm/@observablehq/plot@0.6/+esm";
</script>
```

### API do motor

```javascript
// vizEngine.js

/**
 * Analisa os dados e retorna um array de specs de visualização
 * @param {Object} data - JSON completo (meta + linhas)
 * @returns {VizSpec[]}
 */
function analyzeAndPlan(data) → VizSpec[]

/**
 * Renderiza uma spec num container DOM
 * @param {VizSpec} spec
 * @param {HTMLElement} container
 */
function renderViz(spec, container)

/**
 * Orquestra: analisa + renderiza todos
 * @param {Object} data
 * @param {HTMLElement} root
 */
function renderDashboard(data, root)
```

### VizSpec (estrutura interna)

```javascript
{
  type: "donut" | "barX" | "barY" | "timeline" | "kpi" | "heatmap" | "treemap" | "progress" | "table",
  title: "Distribuição de Status",
  field: "status",               // campo-fonte
  groupBy: "eixo",               // agrupamento (opcional)
  dataType: "categorical_finite",
  priority: 2,                   // ordem no layout
  data: [...],                   // dados já agregados para este viz
  options: {                     // opções Observable Plot
    color: { scheme: "Observable10" },
    sort: { x: "-y" },
    ...
  }
}
```

---

## Identidade Visual: Gov Hub

Toda a interface e visualizações seguem a identidade visual do [Gov Hub](https://gov-hub.io/).

### Paleta de cores

```javascript
const GOVHUB = {
  // Primárias
  primary:       "#7A34F3",  // Roxo Gov Hub
  primaryLight:  "#8b5cf6",  // Roxo claro (gradiente)
  primaryDark:   "#5B21B6",  // Roxo escuro (hover)
  gradient:      "linear-gradient(135deg, #7A34F3 0%, #8b5cf6 100%)",

  // Neutras
  white:         "#FFFFFF",
  bg:            "#F8F9FC",  // Fundo geral (cinza levíssimo com tom frio)
  card:          "#FFFFFF",
  border:        "#E5E7EB",
  textDark:      "#1F2937",  // Títulos
  textMid:       "#6B7280",  // Texto secundário
  textLight:     "#9CA3AF",  // Labels, placeholders

  // Semânticas (status)
  ok:            "#10B981",  // Verde (concluído)
  okBg:          "#ECFDF5",
  warn:          "#F59E0B",  // Amarelo (em risco)
  warnBg:        "#FFFBEB",
  err:           "#EF4444",  // Vermelho (bloqueado)
  errBg:         "#FEF2F2",
  info:          "#7A34F3",  // Roxo primário (em andamento)
  infoBg:        "#F3EFFE",
  neutral:       "#9CA3AF",  // Cinza (não iniciado)
  neutralBg:     "#F3F4F6",
};
```

### Mapeamento Status → Cores Gov Hub

```javascript
const PALETTES = {
  status: {
    concluido:    "#10B981",  // Verde
    em_andamento: "#7A34F3",  // Roxo primário Gov Hub
    em_risco:     "#F59E0B",  // Amarelo
    bloqueado:    "#EF4444",  // Vermelho
    nao_iniciado: "#9CA3AF",  // Cinza
  },
  prioridade: {
    alta:  "#EF4444",  // Vermelho
    media: "#F59E0B",  // Amarelo
    baixa: "#10B981",  // Verde
  }
};
```

### Tipografia

```css
/* Fonte principal: Inter (consistente com Gov Hub) */
body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Títulos de destaque */
h1, .kpi-val {
  font-family: 'Inter', sans-serif;
  font-weight: 700;
}

/* Tamanhos */
--font-xs:  11px;  /* labels, badges */
--font-sm:  12px;  /* corpo da tabela, filtros */
--font-md:  14px;  /* texto principal */
--font-lg:  18px;  /* subtítulos */
--font-xl:  24px;  /* título do dashboard */
--font-kpi: 28px;  /* números KPI */
```

### Gradientes e superfícies

```css
/* Header Gov Hub */
.hdr-title-bar {
  background: linear-gradient(135deg, #7A34F3 0%, #8b5cf6 100%);
}

/* Cards (sombra sutil com tom roxo) */
.card {
  box-shadow: 0 1px 3px rgba(122, 52, 243, 0.06);
}
.card:hover {
  box-shadow: 0 4px 12px rgba(122, 52, 243, 0.1);
}

/* KPI accent bar */
.kpi::before {
  background: linear-gradient(90deg, #7A34F3, #8b5cf6);
}
```

### Esquema de cores para gráficos

Para campos dinâmicos (sem semântica fixa), o motor usa uma escala baseada no roxo Gov Hub:

```javascript
const GOVHUB_SCALE = [
  "#7A34F3",  // Roxo primário
  "#10B981",  // Verde
  "#F59E0B",  // Amarelo
  "#3B82F6",  // Azul
  "#EF4444",  // Vermelho
  "#8b5cf6",  // Roxo claro
  "#14B8A6",  // Teal
  "#F97316",  // Laranja
  "#6366F1",  // Indigo
  "#EC4899",  // Pink
];
```

Para Observable Plot:
```javascript
Plot.plot({
  color: { range: GOVHUB_SCALE }
})
```

---

## Responsividade

### Princípios

1. **Mobile-first**: estilos base para tela pequena; media queries adicionam complexidade para telas maiores.
2. **Conteúdo acessível sem scroll horizontal** (exceto tabelas de dados).
3. **Touch-friendly**: alvos de toque ≥ 44×44 px; espaçamento adequado entre elementos interativos.
4. **Gráficos redimensionáveis**: Observable Plot recalcula `width` via `ResizeObserver`.
5. **Hierarquia visual preservada** em todos os breakpoints: KPIs → gráficos → tabela detalhada.

### Breakpoints

| Token | Range | Uso |
|-------|-------|-----|
| `--bp-sm` | < 640px | Smartphones portrait |
| `--bp-md` | 640px – 1023px | Smartphones landscape / tablets portrait |
| `--bp-lg` | 1024px – 1439px | Tablets landscape / laptops |
| `--bp-xl` | ≥ 1440px | Desktop / monitores |

### Layout por breakpoint

#### Mobile (< 640px)
```
┌─────────────────────────┐
│ [Logo] [Logo] ... [date]│  ← logos sem texto, só ícones
├─────────────────────────┤
│ ████ Título GT ████████ │  ← header roxo, título 14px
├─────────────────────────┤
│ ┌─────────┐ ┌─────────┐ │
│ │ KPI 1   │ │ KPI 2   │ │  ← grid 2 colunas
│ └─────────┘ └─────────┘ │
│ ┌─────────┐ ┌─────────┐ │
│ │ KPI 3   │ │ KPI 4   │ │
│ └─────────┘ └─────────┘ │
├─────────────────────────┤
│ [Donut: status]         │  ← full-width, legenda abaixo
├─────────────────────────┤
│ [Barras: progresso]     │  ← full-width
├─────────────────────────┤
│ [Filtros: scroll horiz] │  ← pills com scroll horizontal
├─────────────────────────┤
│ ┌─ Eixo 1 ───────────┐ │  ← cards colapsados
│ │ ▶ nome   [XX%]      │ │
│ └─────────────────────┘ │
│   └─ Tabela (scroll-x) │  ← tabela com scroll horizontal
└─────────────────────────┘
```

#### Tablet (640px – 1023px)
```
┌─────────────────────────────────────┐
│ [Logo+texto] [Logo+texto] [date]    │
├─────────────────────────────────────┤
│ ██████ Título GT ██████████████████ │
├─────────────────────────────────────┤
│ ┌───────┐ ┌───────┐ ┌───────┐      │
│ │ KPI 1 │ │ KPI 2 │ │ KPI 3 │      │  ← grid 3 colunas
│ └───────┘ └───────┘ └───────┘      │
├─────────────────────────────────────┤
│ [Donut: status]                     │  ← full-width
├─────────────────────────────────────┤
│ [Barras: progresso por eixo]        │  ← full-width
├─────────────────────────────────────┤
│ [Filtros inline] [🔍 Busca]        │
├─────────────────────────────────────┤
│ Eixo cards com barra mini visível   │
└─────────────────────────────────────┘
```

#### Desktop (≥ 1024px)
```
┌──────────────────────────────────────────────────┐
│ [Logos + textos completos]              [date]   │
├──────────────────────────────────────────────────┤
│ ██████████ Título GT ████████████████████████████│
├──────────────────────────────────────────────────┤
│ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐        │
│ │KPI1 │ │KPI2 │ │KPI3 │ │KPI4 │ │KPI5 │        │  ← auto-fit
│ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘        │
├─────────────────────┬────────────────────────────┤
│ [Donut]             │ [Barras progresso]         │  ← grid 1fr 2fr
├─────────────────────┴────────────────────────────┤
│ [Filtros inline] [🔍 Busca]                     │
├──────────────────────────────────────────────────┤
│ Eixo cards com barra mini + stats               │
└──────────────────────────────────────────────────┘
```

### Componentes responsivos

#### Header institucional
| Elemento | Mobile | Tablet | Desktop |
|----------|--------|--------|---------|
| Logo marks | 28×28px, sem texto | 32×32px, com texto | 36×36px, com texto |
| Separadores | hidden | visible | visible |
| Título h1 | 14px | 16px | 18px |
| Botões (Expandir/Recolher) | hidden | visible | visible |
| Badge data | 10px | 12px | 12px |

#### KPI cards
| Breakpoint | Colunas | Padding | Font KPI |
|------------|---------|---------|----------|
| < 640px | 2 | 12px 14px | 22px |
| 640–1023px | 3 | 14px 16px | 24px |
| ≥ 1024px | auto-fit (min 180px) | 18px 20px | 28px |

#### Gráficos (Observable Plot)
| Breakpoint | Layout | Comportamento |
|------------|--------|---------------|
| < 640px | 1 coluna, full-width | `width` = container width via ResizeObserver |
| 640–1023px | 1 coluna, full-width | Donut + legenda side-by-side |
| ≥ 1024px | 2 colunas (1fr 2fr) | Donut à esquerda, barras à direita |

```javascript
// ResizeObserver para gráficos responsivos
function observeResize(container, renderFn) {
  const ro = new ResizeObserver(entries => {
    for (const entry of entries) {
      const width = entry.contentRect.width;
      if (width > 0) renderFn(width);
    }
  });
  ro.observe(container);
  return ro;
}
```

#### Filtros
| Breakpoint | Comportamento |
|------------|---------------|
| < 640px | Scroll horizontal (overflow-x: auto), busca full-width abaixo |
| 640–1023px | Flex wrap, busca ao lado |
| ≥ 1024px | Inline com busca à direita (margin-left: auto) |

#### Eixo cards
| Breakpoint | Stats mini | Tabela interna |
|------------|------------|----------------|
| < 640px | Hidden (só %) | Scroll horizontal, font 11px |
| 640–1023px | Visível | Scroll horizontal se > 5 colunas |
| ≥ 1024px | Visível + badge contagem | Full-width |

#### Tabela de tarefas
```css
/* Mobile: tabela com scroll horizontal */
@media (max-width: 639px) {
  .tab-area { overflow-x: auto; -webkit-overflow-scrolling: touch; }
  .tbl { min-width: 600px; }
  .tbl td, .tbl th { padding: 6px 8px; font-size: 11px; }
}
```

#### Footer
| Breakpoint | Layout | Colunas |
|------------|--------|---------|
| < 640px | Stack vertical | 1 coluna |
| 640–1023px | Stack vertical | 1 coluna |
| ≥ 1024px | Grid | 2fr 1fr 1fr |

### Gráficos: regras de resize

Observable Plot deve recalcular ao redimensionar:

```javascript
// No vizEngine.js, cada gráfico se auto-redimensiona
function renderResponsiveChart(spec, container) {
  let chart = null;
  const render = (width) => {
    if (chart) chart.remove();
    spec.options.width = width;
    chart = Plot.plot(spec.options);
    container.querySelector('.viz-body').appendChild(chart);
  };
  observeResize(container, render);
}
```

### Touch & acessibilidade

- **Alvos de toque**: min 44×44px para filtros, botões, links
- **Donut hover**: substituído por tap no mobile (toggle tooltip)
- **Swipe**: cards de eixo suportam swipe para expandir/recolher (futuro)
- **Contraste**: todas as combinações cor/fundo mantêm WCAG AA (4.5:1 para texto, 3:1 para UI)
- **Focus visible**: outline 2px roxo (`#7A34F3`) com offset 2px em todos os interativos
- **Reduced motion**: respeita `prefers-reduced-motion` para animações

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## Limitações e fallbacks

| Cenário | Comportamento |
|---|---|
| Campo com 100% valores vazios | Não gera visualização |
| Menos de 2 data points num campo numérico | Mostra como KPI em vez de gráfico |
| Todos os prazos "em aberto" | Não gera timeline; mostra nota "Sem dados temporais" |
| > 50 categorias num campo open | Mostra top 15 + "outros" |
| Observable Plot falha ao carregar (CDN) | Fallback para D3.js puro (gráficos atuais) |

---

## Implementação (fases)

### Fase 1 — Detecção + layout (MVP)
- [ ] `vizEngine.js`: função `inferType()` + `analyzeAndPlan()`
- [ ] Mapeamento fixo dos 5 campos atuais → visualizações existentes
- [ ] Integrar Observable Plot via CDN
- [ ] Manter gráficos atuais funcionando com nova engine

### Fase 2 — Campos dinâmicos
- [ ] Detecção de campos fora do `KNOWN_FIELDS`
- [ ] Renderização automática de gráficos secundários
- [ ] Suporte a `numeric_currency` (barras ordenadas)

### Fase 3 — Temporal
- [ ] Timeline/Gantt quando prazos tiverem datas reais
- [ ] Heatmap de status ao longo do tempo (se houver histórico)

### Fase 4 — Avançado
- [ ] Treemap para distribuição orçamentária
- [ ] Sunburst para hierarquia Eixo→Processo→Tarefa
- [ ] Sparklines nos KPI cards (tendência)

---

## Exemplo: como o motor processaria os dados atuais

Dado o `acoes.json` atual:

```
Campos detectados:
  status     → categorical_finite (5 valores) → DONUT
  prioridade → categorical_finite (3 valores) → descartado (pouco variação)
  progresso  → numeric_percent               → BARRAS DE PROGRESSO por eixo
  resp       → categorical_open (3 valores)  → BARRAS (quem tem mais tarefas)
  prazo      → temporal_date (mas todos "em aberto") → SKIP

Layout gerado:
  1. KPI cards: total tarefas, % concluído, bloqueadas, progresso médio
  2. Donut: status
  3. Barras horizontais: progresso por Eixo Temático
  4. (NOVO) Barras: tarefas por Responsável
  5. Tabela: detalhes hierárquicos
```

---

## Decisões de design

- **Frontend-only**: Todo processamento no browser. Sem server, sem build step.
- **Observable Plot**: Declarativo, menos código que D3 puro, mesma qualidade visual.
- **Progressivo**: A engine não quebra o dashboard existente — ela o substitui incrementalmente.
- **Zero-config**: Nenhum arquivo de configuração necessário. O JSON é a única fonte de verdade.
