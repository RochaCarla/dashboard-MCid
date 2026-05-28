/**
 * vizEngine.js — Motor de Visualização Adaptativa (Fase 1)
 * Analisa dados do JSON e gera visualizações automaticamente via Observable Plot.
 * Identidade Visual: Gov Hub (https://gov-hub.io/)
 */

// ── Gov Hub Design Tokens ────────────────────────────────────────────────────
const GOVHUB = {
  primary:      "#7A34F3",
  primaryLight: "#8b5cf6",
  primaryDark:  "#5B21B6",
  gradient:     "linear-gradient(135deg, #7A34F3 0%, #8b5cf6 100%)",
  bg:           "#F8F9FC",
  card:         "#FFFFFF",
  border:       "#E5E7EB",
  textDark:     "#1F2937",
  textMid:      "#6B7280",
  textLight:    "#9CA3AF",
  ok:           "#10B981",
  okBg:         "#ECFDF5",
  warn:         "#F59E0B",
  warnBg:       "#FFFBEB",
  err:          "#EF4444",
  errBg:        "#FEF2F2",
  info:         "#7A34F3",
  infoBg:       "#F3EFFE",
  neutral:      "#9CA3AF",
  neutralBg:    "#F3F4F6",
};

const GOVHUB_SCALE = [
  "#7A34F3", "#10B981", "#F59E0B", "#3B82F6", "#EF4444",
  "#8b5cf6", "#14B8A6", "#F97316", "#6366F1", "#EC4899",
];

const STATUS_COLORS = {
  concluido:    GOVHUB.ok,
  em_andamento: GOVHUB.primary,
  em_risco:     GOVHUB.warn,
  bloqueado:    GOVHUB.err,
  nao_iniciado: GOVHUB.neutral,
};

const PRIO_COLORS = {
  alta:  GOVHUB.err,
  media: GOVHUB.warn,
  baixa: GOVHUB.ok,
};

// ── Campos conhecidos (schema base) ──────────────────────────────────────────
const KNOWN_FIELDS = [
  "id", "desc", "resp", "status", "prioridade",
  "progresso", "prazo", "notas", "atividade", "processo", "linhaId"
];

// ── Detecção de tipo ─────────────────────────────────────────────────────────
function inferType(fieldName, values) {
  const nonEmpty = values.filter(v => v !== null && v !== undefined && v !== "");
  if (!nonEmpty.length) return "empty";

  // Temporal
  if (nonEmpty.every(v => /^\d{4}-\d{2}-\d{2}/.test(String(v)))) return "temporal_date";

  // Numérico
  if (nonEmpty.every(v => typeof v === "number" || (!isNaN(Number(v)) && String(v).trim() !== ""))) {
    const nums = nonEmpty.map(Number);
    const max = Math.max(...nums);
    const min = Math.min(...nums);
    if (min >= 0 && max <= 100 && /progress|progresso/i.test(fieldName))
      return "numeric_percent";
    if (/orçamento|orcamento|valor|custo|budget|investimento/i.test(fieldName))
      return "numeric_currency";
    if (Number.isInteger(max) && max < 1000) return "numeric_count";
    return "numeric_percent";
  }

  // Categórico
  const uniq = new Set(nonEmpty.map(v => String(v).toLowerCase().trim()));
  if (uniq.size <= 7) return "categorical_finite";
  if (uniq.size <= 20) return "categorical_open";

  return "text";
}

// ── Análise e planejamento ───────────────────────────────────────────────────
function analyzeAndPlan(data) {
  const allTarefas = extractAllTarefas(data);
  if (!allTarefas.length) return [];

  const specs = [];
  let priority = 0;

  // 1. KPIs (sempre)
  specs.push(buildKpiSpec(data, allTarefas, priority++));

  // 2. Status distribution (donut)
  specs.push(buildStatusDonutSpec(allTarefas, priority++));

  // 3. Progresso por eixo (barras)
  specs.push(buildProgressBarsSpec(data, priority++));

  // 4. Distribuição por responsável (se > 1 responsável)
  const resps = [...new Set(allTarefas.map(t => t.resp).filter(Boolean))];
  if (resps.length > 1) {
    specs.push(buildRespBarSpec(allTarefas, resps, priority++));
  }

  // 5. Timeline (se houver datas reais)
  const datesReal = allTarefas.filter(t => t.prazo && !/aberto/i.test(t.prazo) && /^\d{4}-\d{2}-\d{2}/.test(t.prazo));
  if (datesReal.length >= 2) {
    specs.push(buildTimelineSpec(datesReal, priority++));
  }

  // 6. Campos dinâmicos
  const dynamicFields = detectDynamicFields(allTarefas);
  dynamicFields.forEach(({ field, type, values }) => {
    const spec = buildDynamicSpec(field, type, values, allTarefas, priority++);
    if (spec) specs.push(spec);
  });

  return specs.sort((a, b) => a.priority - b.priority);
}

// ── Extração de tarefas (v1 e v2) ───────────────────────────────────────────
function extractAllTarefas(data) {
  const schema = data.meta?.schema || (data.linhas[0]?.processos ? "v2" : "v1");
  if (schema === "v2") {
    return data.linhas.flatMap(l =>
      l.processos.flatMap(p =>
        p.tarefas.map(t => ({ ...t, eixo: l.nome, processo: p.processo }))
      )
    );
  }
  return data.linhas.flatMap(l =>
    (l.acoes || []).map(a => ({ ...a, eixo: l.nome }))
  );
}

// ── Builders de spec ─────────────────────────────────────────────────────────

function buildKpiSpec(data, allTarefas, priority) {
  const total = allTarefas.length;
  const done = allTarefas.filter(t => t.status === "concluido").length;
  const prog = allTarefas.filter(t => t.status === "em_andamento").length;
  const risk = allTarefas.filter(t => t.status === "bloqueado" || t.status === "em_risco").length;
  const avg = total ? Math.round(allTarefas.reduce((s, t) => s + (t.progresso || 0), 0) / total) : 0;

  return {
    type: "kpi",
    title: "Indicadores",
    priority,
    data: [
      { label: "Total de tarefas", value: total, detail: `em ${data.linhas.length} eixos`, accent: "primary" },
      { label: "Progresso geral", value: avg + "%", detail: "média ponderada", accent: "primary" },
      { label: "Concluídas", value: done, detail: `${total ? Math.round(done / total * 100) : 0}% do total`, accent: "ok" },
      { label: "Em andamento", value: prog, detail: `${total ? Math.round(prog / total * 100) : 0}% do total`, accent: "warn" },
      { label: "Bloqueadas / Risco", value: risk, detail: "requerem atenção", accent: "err" },
    ]
  };
}

function buildStatusDonutSpec(allTarefas, priority) {
  const counts = {};
  allTarefas.forEach(t => { counts[t.status] = (counts[t.status] || 0) + 1; });
  return {
    type: "donut",
    title: "Status das Tarefas",
    field: "status",
    dataType: "categorical_finite",
    priority,
    data: Object.entries(counts).filter(([, v]) => v > 0),
    options: { colors: STATUS_COLORS }
  };
}

function buildProgressBarsSpec(data, priority) {
  const rows = data.linhas.map(l => {
    const tarefas = l.processos
      ? l.processos.flatMap(p => p.tarefas)
      : (l.acoes || []);
    const avg = tarefas.length
      ? Math.round(tarefas.reduce((s, t) => s + (t.progresso || 0), 0) / tarefas.length)
      : 0;
    return { nome: l.nome, progresso: avg };
  });

  return {
    type: "barX",
    title: "Progresso por Eixo Temático",
    field: "progresso",
    groupBy: "eixo",
    dataType: "numeric_percent",
    priority,
    data: rows,
    options: { domain: [0, 100], colorFn: progressColor }
  };
}

function buildRespBarSpec(allTarefas, resps, priority) {
  const counts = {};
  allTarefas.forEach(t => { if (t.resp) counts[t.resp] = (counts[t.resp] || 0) + 1; });
  const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 15);

  return {
    type: "barX",
    title: "Tarefas por Responsável",
    field: "resp",
    dataType: "categorical_open",
    priority,
    data: sorted.map(([nome, count]) => ({ nome, count })),
    options: { color: GOVHUB.primary }
  };
}

function buildTimelineSpec(tarefas, priority) {
  return {
    type: "timeline",
    title: "Linha do Tempo (Prazos)",
    field: "prazo",
    dataType: "temporal_date",
    priority,
    data: tarefas.map(t => ({
      desc: t.desc,
      prazo: t.prazo,
      status: t.status,
      resp: t.resp
    })),
    options: { colors: STATUS_COLORS }
  };
}

function buildDynamicSpec(field, type, values, allTarefas, priority) {
  const title = field.charAt(0).toUpperCase() + field.slice(1).replace(/_/g, " ");

  if (type === "categorical_finite") {
    const counts = {};
    allTarefas.forEach(t => {
      const v = t[field];
      if (v) counts[v] = (counts[v] || 0) + 1;
    });
    return {
      type: Object.keys(counts).length <= 5 ? "donut" : "barX",
      title,
      field,
      dataType: type,
      priority,
      data: Object.entries(counts).filter(([, v]) => v > 0),
      options: { colorScale: GOVHUB_SCALE }
    };
  }

  if (type === "numeric_currency" || type === "numeric_count") {
    const rows = allTarefas
      .filter(t => t[field] != null && t[field] !== "")
      .map(t => ({ label: t.desc || t.atividade || "–", value: Number(t[field]) }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 15);
    return {
      type: "barX",
      title,
      field,
      dataType: type,
      priority,
      data: rows,
      options: { color: GOVHUB.primary }
    };
  }

  return null;
}

// ── Detecção de campos dinâmicos ─────────────────────────────────────────────
function detectDynamicFields(allTarefas) {
  if (!allTarefas.length) return [];
  const fields = Object.keys(allTarefas[0]).filter(k => !KNOWN_FIELDS.includes(k));
  return fields.map(field => {
    const values = allTarefas.map(t => t[field]);
    const type = inferType(field, values);
    return { field, type, values };
  }).filter(f => f.type !== "empty" && f.type !== "text");
}

// ── Utilitários ──────────────────────────────────────────────────────────────
function progressColor(p) {
  if (p >= 75) return GOVHUB.ok;
  if (p >= 40) return GOVHUB.primary;
  if (p >= 10) return GOVHUB.warn;
  return GOVHUB.neutral;
}

// ── Renderização com Observable Plot ─────────────────────────────────────────
async function renderViz(spec, container) {
  const el = document.createElement("div");
  el.className = "viz-card";
  el.innerHTML = `<h3 class="viz-title">${spec.title}</h3><div class="viz-body"></div>`;
  container.appendChild(el);
  const body = el.querySelector(".viz-body");

  switch (spec.type) {
    case "kpi":
      renderKpiCards(spec, body);
      break;
    case "donut":
      await renderDonutPlot(spec, body);
      break;
    case "barX":
      await renderBarXPlot(spec, body);
      break;
    case "timeline":
      await renderTimelinePlot(spec, body);
      break;
    default:
      body.innerHTML = `<p style="color:${GOVHUB.textLight}">Visualização "${spec.type}" pendente.</p>`;
  }
}

function renderKpiCards(spec, body) {
  const accentMap = { primary: GOVHUB.primary, ok: GOVHUB.ok, warn: GOVHUB.warn, err: GOVHUB.err };
  body.style.display = "grid";
  body.style.gridTemplateColumns = "repeat(auto-fit, minmax(160px, 1fr))";
  body.style.gap = "12px";
  body.innerHTML = spec.data.map(k => `
    <div class="viz-kpi" style="border-top:3px solid ${accentMap[k.accent] || GOVHUB.primary}">
      <div class="viz-kpi-lbl">${k.label}</div>
      <div class="viz-kpi-val">${k.value}</div>
      <div class="viz-kpi-det">${k.detail}</div>
    </div>
  `).join("");
}

async function renderDonutPlot(spec, body) {
  if (typeof Plot === "undefined") {
    body.innerHTML = "<p>Observable Plot não carregado.</p>";
    return;
  }
  const data = spec.data.map(([key, value]) => ({ key, value }));
  const colors = spec.options.colors || {};
  const chart = Plot.plot({
    width: 260,
    height: 260,
    margin: 10,
    marks: [
      Plot.barY(data, {
        x: "key",
        y: "value",
        fill: d => colors[d.key] || GOVHUB_SCALE[data.indexOf(d) % GOVHUB_SCALE.length],
        tip: true,
      }),
      Plot.ruleY([0]),
    ],
    x: { label: null, tickFormat: d => STATUS_LABELS[d] || d },
    y: { label: "Quantidade" },
    color: { legend: false },
    style: { fontFamily: "Inter, sans-serif", fontSize: 12 },
  });
  body.appendChild(chart);
}

async function renderBarXPlot(spec, body) {
  if (typeof Plot === "undefined") {
    body.innerHTML = "<p>Observable Plot não carregado.</p>";
    return;
  }
  const data = spec.data;
  const nameKey = data[0]?.nome !== undefined ? "nome" : "label";
  const valKey = data[0]?.progresso !== undefined ? "progresso" : (data[0]?.count !== undefined ? "count" : "value");

  const chart = Plot.plot({
    width: body.clientWidth || 500,
    height: Math.max(data.length * 28 + 40, 120),
    marginLeft: 160,
    marks: [
      Plot.barX(data, {
        y: nameKey,
        x: valKey,
        fill: d => spec.options.colorFn ? spec.options.colorFn(d[valKey]) : (spec.options.color || GOVHUB.primary),
        tip: true,
        sort: { y: "-x" },
      }),
      Plot.ruleX([0]),
    ],
    x: { label: null, domain: spec.options.domain || undefined },
    y: { label: null },
    style: { fontFamily: "Inter, sans-serif", fontSize: 11 },
  });
  body.appendChild(chart);
}

async function renderTimelinePlot(spec, body) {
  if (typeof Plot === "undefined") {
    body.innerHTML = "<p>Observable Plot não carregado.</p>";
    return;
  }
  const data = spec.data
    .filter(d => d.prazo)
    .map(d => ({ ...d, date: new Date(d.prazo) }))
    .sort((a, b) => a.date - b.date);

  const chart = Plot.plot({
    width: body.clientWidth || 600,
    height: 200,
    marginLeft: 40,
    marks: [
      Plot.dot(data, {
        x: "date",
        y: () => 0,
        fill: d => STATUS_COLORS[d.status] || GOVHUB.neutral,
        r: 6,
        tip: true,
        title: d => `${d.desc}\n${d.resp}\n${d.prazo}`,
      }),
      Plot.ruleY([0], { stroke: GOVHUB.border }),
    ],
    x: { label: null, type: "time" },
    y: { axis: null },
    style: { fontFamily: "Inter, sans-serif", fontSize: 11 },
  });
  body.appendChild(chart);
}

// ── Labels para exibição ─────────────────────────────────────────────────────
const STATUS_LABELS = {
  concluido: "Concluído",
  em_andamento: "Em andamento",
  em_risco: "Em risco",
  bloqueado: "Bloqueado",
  nao_iniciado: "Não iniciado",
};

// ── Orquestrador principal ───────────────────────────────────────────────────
async function renderDashboard(data, root) {
  const specs = analyzeAndPlan(data);
  root.innerHTML = "";
  for (const spec of specs) {
    await renderViz(spec, root);
  }
}

// ── Exportar para uso global ─────────────────────────────────────────────────
window.VizEngine = {
  analyzeAndPlan,
  renderViz,
  renderDashboard,
  inferType,
  GOVHUB,
  GOVHUB_SCALE,
  STATUS_COLORS,
};
