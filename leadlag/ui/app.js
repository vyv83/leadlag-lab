// Path-prefix aware: strip "/ui/..." off current pathname to get the mount base
// (empty string when served at root, "/leadlag-lab" when served behind nginx).
const BASE = (location.pathname.match(/^(.*?)\/ui\//) || ["", ""])[1];
function api(path) { return BASE + (path.startsWith("/") ? path : "/" + path); }
function apiFetch(path, init) { return fetch(api(path), init); }

async function fetchJSON(url) {
  const full = url.startsWith("/api") ? api(url) : url;
  const r = await fetch(full);
  if (!r.ok) throw new Error(`${full}: ${r.status}`);
  return r.json();
}
function qs(k) { return new URLSearchParams(location.search).get(k); }
function el(tag, attrs = {}, kids = []) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "html") e.innerHTML = v; else e.setAttribute(k, v);
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
