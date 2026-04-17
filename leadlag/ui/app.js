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
      else td.textContent = c == null ? "—" : String(c);
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
