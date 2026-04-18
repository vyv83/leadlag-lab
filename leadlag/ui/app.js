// Path-prefix aware: strip "/ui/..." off current pathname to get the mount base
// (empty string when served at root, "/leadlag-lab" when served behind nginx).
const BASE = (location.pathname.match(/^(.*?)\/ui\//) || ["", ""])[1];
function api(path) { return BASE + (path.startsWith("/") ? path : "/" + path); }
function apiFetch(path, init) { return fetch(api(path), init); }

async function fetchJSON(url) {
  const full = url.startsWith("/api") ? api(url) : url;
  const r = await fetch(full);
  if (!r.ok) {
    let detail = "";
    try { detail = JSON.stringify(await r.json()); } catch (_) { detail = await r.text(); }
    throw new Error(`${full}: ${r.status} ${detail}`);
  }
  return r.json();
}
async function postJSON(url, body) {
  const full = url.startsWith("/api") ? api(url) : url;
  const r = await fetch(full, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  if (!r.ok) {
    let detail = "";
    try { detail = JSON.stringify(await r.json()); } catch (_) { detail = await r.text(); }
    throw new Error(`${full}: ${r.status} ${detail}`);
  }
  return r.json();
}

/* ── Shared helpers ── */
function qs(k) { return new URLSearchParams(location.search).get(k); }
function setQS(params) {
  const u = new URL(location.href);
  for (const [k, v] of Object.entries(params)) {
    if (v === null || v === undefined || v === "") u.searchParams.delete(k);
    else u.searchParams.set(k, v);
  }
  history.replaceState(null, "", u.toString());
}
function el(tag, attrs = {}, kids = []) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "html") e.innerHTML = v;
    else if (k === "className") e.className = v;
    else if (k.startsWith("on") && typeof v === "function") e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v);
  }
  for (const c of [].concat(kids)) e.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
  return e;
}
function linkTo(href, text) {
  const a = el("a", { href }); a.textContent = text; return a;
}
function fmt(x, d = 2) {
  if (x === null || x === undefined) return "—";
  if (typeof x !== "number") return String(x);
  return x.toFixed(d);
}
function pct(x) { return x == null ? "—" : (100 * x).toFixed(1) + "%"; }
function utc(ts) {
  if (ts === null || ts === undefined || ts === "") return "—";
  const d = new Date(Number(ts));
  if (Number.isNaN(d.getTime())) return String(ts);
  return d.toISOString().slice(11, 23) + " UTC";
}
function signed(x, d = 2) {
  if (x === null || x === undefined || typeof x !== "number") return fmt(x, d);
  return (x >= 0 ? "+" : "") + x.toFixed(d);
}
function fillTable(sel, rows, rowFn) {
  const tbody = document.querySelector(`${sel} tbody`);
  tbody.innerHTML = "";
  for (const r of rows) {
    const tr = el("tr");
    for (const c of rowFn(r)) {
      const td = el("td");
      if (c instanceof Node) td.appendChild(c);
      else setValueContent(td, c == null ? "—" : c);
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
}
function showError(sel, err) {
  const node = typeof sel === "string" ? document.querySelector(sel) : sel;
  if (node) node.innerHTML = `<div class="error">${err.message || err}</div>`;
}
function setActiveButton(group, value) {
  document.querySelectorAll(`[data-group="${group}"]`).forEach(btn => {
    btn.classList.toggle("active", btn.dataset.value === value);
  });
}
function priceToBps(values, base) {
  return values.map(v => (v === null || v === undefined || !base) ? null : (Number(v) / base - 1) * 10000);
}
function firstNumber(values) {
  for (const v of values || []) {
    if (v !== null && v !== undefined && Number.isFinite(Number(v))) return Number(v);
  }
  return null;
}

/* ── Shared Plotly config ── */
const PLOT_LAYOUT = {
  paper_bgcolor: "#0e1117",
  plot_bgcolor: "#0e1117",
  font: { color: "#c9d1d9", size: 10 },
  margin: { t: 48, r: 50, b: 36, l: 50 },
  dragmode: "pan",
  title: { font: { size: 12 } },
  legend: {
    orientation: "h",
    y: 1.02,
    yanchor: "bottom",
    font: { size: 9 },
  },
};
const PLOT_CFG = {
  responsive: true,
  displayModeBar: "hover",
  displaylogo: false,
  modeBarButtons: [["zoomIn2d", "zoomOut2d", "resetScale2d"]],
};

function fillCards(id, rows) {
  const box = document.getElementById(id);
  box.innerHTML = "";
  rows.forEach(([label, value]) => {
    const card = el("div", { class: "metric-card" }, [
      el("div", { class: "metric-label" }, [label]),
    ]);
    card.appendChild(setValueContent(el("div", { class: "metric-value" }), value));
    box.appendChild(card);
  });
}
function seconds(s) {
  s = Number(s || 0);
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = Math.floor(s % 60);
  return h ? `${h}h ${m}m` : `${m}m ${sec}s`;
}
function humanBytes(x) {
  x = Number(x || 0);
  if (x >= 1e9) return `${fmt(x / 1e9, 2)} GB`;
  if (x >= 1e6) return `${fmt(x / 1e6, 2)} MB`;
  if (x >= 1e3) return `${fmt(x / 1e3, 2)} KB`;
  return `${fmt(x, 0)} B`;
}

/* ── Signal badge helper ── */
function sigBadge(signal) {
  const s = { A: "sig-a", B: "sig-b", C: "sig-c" }[signal];
  return s ? `<span class="sig ${s}">${signal}</span>` : signal;
}
function dirArrow(direction) {
  return Number(direction) > 0
    ? '<span class="dir-up">▲</span>'
    : '<span class="dir-down">▼</span>';
}
function checkMark(v) { return v ? '<span class="ok">✓</span>' : '<span class="no">✗</span>'; }
function naMark(v) { return v ? '<span class="ok">✓</span>' : '<span class="na">—</span>'; }
function setValueContent(node, value) {
  if (typeof value === "string" && /^<span class="(ok|no|na|sig|dir-)/.test(value)) {
    node.innerHTML = value;
  } else {
    node.textContent = String(value);
  }
  return node;
}

function attachVisibleYFit(chart, traces, axisKeys = ["yaxis", "yaxis2"]) {
  if (!chart || typeof chart.on !== "function") return;
  chart.removeAllListeners && chart.removeAllListeners("plotly_relayout");
  chart.on("plotly_relayout", () => fitVisibleY(chart, traces, axisKeys));
  setTimeout(() => fitVisibleY(chart, traces, axisKeys), 0);
}

function fitVisibleY(chart, traces, axisKeys) {
  if (chart._fittingVisibleY) return;
  const range = chart && chart._fullLayout && chart._fullLayout.xaxis && chart._fullLayout.xaxis.range;
  if (!range || range.length < 2) return;
  const a = plotXNumber(range[0]);
  const b = plotXNumber(range[1]);
  if (!Number.isFinite(a) || !Number.isFinite(b)) return;
  const lo = Math.min(a, b);
  const hi = Math.max(a, b);
  const update = {};
  axisKeys.forEach(axisKey => {
    const values = visibleYValues(traces, axisKey, lo, hi);
    if (!values.length) return;
    let ymin = Math.min(...values);
    let ymax = Math.max(...values);
    const span = ymax - ymin;
    const pad = span > 0 ? span * 0.08 : Math.max(Math.abs(ymin) * 0.02, 1);
    update[`${axisKey}.range`] = [ymin - pad, ymax + pad];
    update[`${axisKey}.autorange`] = false;
  });
  if (Object.keys(update).length) {
    chart._fittingVisibleY = true;
    Plotly.relayout(chart, update).finally(() => { chart._fittingVisibleY = false; });
  }
}

function visibleYValues(traces, axisKey, lo, hi) {
  const values = [];
  traces.forEach(trace => {
    if (trace.visible === false || traceAxisKey(trace) !== axisKey) return;
    (trace.x || []).forEach((x, i) => {
      const xv = plotXNumber(x);
      const yv = Number((trace.y || [])[i]);
      if (Number.isFinite(xv) && xv >= lo && xv <= hi && Number.isFinite(yv)) values.push(yv);
    });
  });
  return values;
}

function traceAxisKey(trace) {
  const axis = trace.yaxis || "y";
  return axis === "y" ? "yaxis" : `yaxis${axis.slice(1)}`;
}

function plotXNumber(x) {
  if (x instanceof Date) return x.getTime();
  if (typeof x === "number") return x;
  const n = Number(x);
  if (Number.isFinite(n)) return n;
  const d = Date.parse(x);
  return Number.isFinite(d) ? d : NaN;
}
