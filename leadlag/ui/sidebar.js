// sidebar.js — Phase 2 Tree Sidebar for LeadLag Lab
// Included after app.js on every page. Uses: fetchJSON, api, qs, el, fmt, signed

(function() {
  "use strict";

  const CACHE_KEY = "sidebar_cache";
  const CACHE_TTL = 30_000; // 30 seconds
  const COLLAPSED_KEY = "sb_collapsed";
  const JOB_DONE_TTL = 12_000;
  let sidebarJobPoll = null;
  let lastSidebarJobKey = "";
  let retainedSidebarJob = null;

  // ── Layout bootstrap ──

  function bootstrap() {
    // Create sidebar element
    const aside = document.createElement("aside");
    aside.className = "sidebar";
    aside.id = "sidebar";
    document.body.prepend(aside);

    // Wrap <main> in .app-main
    const main = document.querySelector("main");
    if (main) {
      const wrap = document.createElement("div");
      wrap.className = "app-main";
      main.parentNode.insertBefore(wrap, main);
      wrap.appendChild(main);
    }
  }

  // ── Data loading ──

  async function loadSidebarData(forceFresh) {
    if (!forceFresh) {
      try {
        const cached = sessionStorage.getItem(CACHE_KEY);
        if (cached) {
          const parsed = JSON.parse(cached);
          if (Date.now() - parsed.ts < CACHE_TTL) return parsed.data;
        }
      } catch (_) {}
    }

    const endpoints = [
      { key: "collections", url: "/api/collections" },
      { key: "sessions", url: "/api/analyses" },
      { key: "strategies", url: "/api/strategies" },
      { key: "backtests", url: "/api/backtests" },
      { key: "backtestStatus", url: "/api/backtests/status" },
      { key: "notebooks", url: "/api/notebooks" },
      { key: "collectorStatus", url: "/api/collector/status" },
      { key: "paperStatus", url: "/api/paper/status" },
      { key: "paperStrategies", url: "/api/paper/strategies" },
    ];

    const results = await Promise.allSettled(
      endpoints.map(ep => fetchJSON(ep.url).then(data => ({ key: ep.key, data })))
    );

    const data = {};
    results.forEach(r => {
      if (r.status === "fulfilled") data[r.value.key] = r.value.data;
      else data[r.status === "rejected" ? null : r.value?.key] = null;
    });

    if (data.backtestStatus && data.backtestStatus.running && data.backtestStatus.job_id) {
      try {
        data.backtestJob = await fetchJSON(`/api/backtest-jobs/${encodeURIComponent(data.backtestStatus.job_id)}`);
      } catch (_) {
        data.backtestJob = null;
      }
    } else {
      data.backtestJob = null;
    }

    sessionStorage.setItem(CACHE_KEY, JSON.stringify({ ts: Date.now(), data }));
    return data;
  }

  // ── Helpers ──

  function isCollapsed(id) {
    try {
      const set = JSON.parse(sessionStorage.getItem(COLLAPSED_KEY) || "{}");
      return !!set[id];
    } catch { return false; }
  }

  function toggleCollapsed(id) {
    let set = {};
    try { set = JSON.parse(sessionStorage.getItem(COLLAPSED_KEY) || "{}"); } catch {}
    set[id] = !set[id];
    sessionStorage.setItem(COLLAPSED_KEY, JSON.stringify(set));
  }

  function analysesForRecording(recId, sessions) {
    const prefix = recId.split("_").slice(0, 3).join("_");
    return (sessions || []).filter(s =>
      s.id.startsWith(prefix) || (s.collection_id && s.collection_id === recId)
    );
  }

  function backtestsForStrategy(name, backtests) {
    return (backtests || []).filter(b => b.strategy === name);
  }

  function sessionLabel(session) {
    const m = (session.id || "").match(/threshold([\d.]+)/);
    const thresh = m ? `σ${m[1]}` : null;
    const nEv = session.n_events || 0;
    return thresh ? `${thresh} · ${nEv}ev` : `${nEv}ev`;
  }

  function hasNotebook(name, notebooks) {
    return (notebooks || []).some(n => n.name === name || n === name);
  }

  function paperForStrategy(name, paperStrategies) {
    return (paperStrategies || []).find(p => p.strategy_name === name || p.name === name);
  }

  function fmtDuration(ms) {
    if (!ms) return "—";
    const s = Math.round(Number(ms) / 1000);
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    if (h > 0) return m > 0 ? `${h}.${m}h` : `${h}h`;
    return `${m}m`;
  }

  function shortDate(ts) {
    if (!ts) return "?";
    const n = Number(ts);
    const d = new Date(isNaN(n) ? ts : n);
    if (isNaN(d.getTime())) return "?";
    const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    return `${months[d.getUTCMonth()]} ${d.getUTCDate()}`;
  }

  function shortDateFromId(id) {
    const m = (id || "").match(/^(\d{4})(\d{2})(\d{2})/);
    if (!m) return "";
    const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    return `${months[parseInt(m[2]) - 1]} ${parseInt(m[3])}`;
  }

  // ── Active page detection ──

  function getActiveInfo() {
    const page = location.pathname.split("/").pop().replace(".html", "");
    return {
      page,
      analysis: qs("analysis"),
      id: qs("id"),
      strategy: qs("strategy"),
      backtest: qs("backtest"),
    };
  }

  // ── Rendering ──

  function renderSidebar(data) {
    const aside = document.getElementById("sidebar");
    if (!aside) return;
    aside.innerHTML = "";

    const active = getActiveInfo();
    const collRunning = data.collectorStatus && data.collectorStatus.running;
    const paperRunning = data.paperStatus && data.paperStatus.running;
    const paperStrategy = data.paperStatus && data.paperStatus.strategy_name;

    // Header
    const header = el("div", { className: "sb-header" });
    header.appendChild(el("a", { href: "dashboard.html" }, ["leadlag"]));
    const refreshBtn = el("span", { className: "sb-refresh", title: "Refresh sidebar" }, ["↺"]);
    refreshBtn.onclick = () => window.refreshSidebar(true);
    header.appendChild(refreshBtn);
    aside.appendChild(header);

    const jobHost = el("div", { id: "sbGlobalJobHost" });
    aside.appendChild(jobHost);
    renderGlobalJobWidget(data.backtestStatus, data.backtestJob || retainedSidebarJob);

    // Static links ordered by user pipeline
    aside.appendChild(makeSectionHeader("PIPELINE"));
    aside.appendChild(makeStaticLink("Dashboard", "dashboard.html", active.page === "dashboard"));
    aside.appendChild(makeStaticLink("Collector", "collector.html", active.page === "collector", collRunning));
    aside.appendChild(makeStaticLink("Recordings", "recordings.html", active.page === "recordings"));
    aside.appendChild(makeStaticLink("Strategies", "strategy.html", active.page === "strategy"));
    aside.appendChild(makeStaticLink("Backtests", "backtest.html", active.page === "backtest"));
    aside.appendChild(makeStaticLink("Monte Carlo", "montecarlo.html", active.page === "montecarlo"));
    aside.appendChild(makeStaticLink("Paper", "paper.html", active.page === "paper", paperRunning, paperStrategy ? `?strategy=${encodeURIComponent(paperStrategy)}` : ""));

    // DATA section
    aside.appendChild(makeSectionHeader("Recordings", "recordings.html"));
    renderDataSection(aside, data, active);

    // RESEARCH section
    aside.appendChild(makeSectionHeader("Research", "strategy.html"));
    renderResearchSection(aside, data, active);

    // Footer: Jupyter
    const footer = el("div", { className: "sb-footer" });
    footer.appendChild(el("a", { href: jupyterLabUrl(), target: "_blank" }, ["Open Jupyter ↗"]));
    aside.appendChild(footer);
  }

  function makeStaticLink(text, href, isActive, isLive, suffix) {
    const row = el("div", { className: "sb-static" + (isActive ? " active" : "") });
    const a = el("a", { href: href + (suffix || "") }, [text]);
    row.appendChild(a);
    if (isLive) {
      const dot = el("span", { className: "sb-live" });
      row.appendChild(dot);
    }
    return row;
  }

  function makeSectionHeader(label, href) {
    const div = el("div", { className: "sb-section" });
    const a = el("a", { href: href || "#", style: "color:inherit;text-decoration:none" }, [label]);
    if (!href) {
      a.onclick = (e) => e.preventDefault();
    }
    a.onmouseover = () => a.style.color = "#8b949e";
    a.onmouseout = () => a.style.color = "";
    div.appendChild(a);
    return div;
  }

  function renderGlobalJobWidget(status, job) {
    const host = document.getElementById("sbGlobalJobHost");
    if (!host) return;
    host.innerHTML = "";
    const running = !!(status && status.running);
    const showRetained = !!(job && !running && retainedSidebarJob && retainedSidebarJob.job_id === job.job_id);
    const progress = Math.max(2, Math.min(100, Math.round((Number(job?.progress) || 0) * 100)));
    if (!running && !job) return;

    const wrap = el("div", { className: "sb-job" });
    wrap.appendChild(el("div", { className: "sb-job-title" }, ["Backtest Job"]));

    const metaParts = [];
    if (status?.strategy_name) metaParts.push(status.strategy_name);
    if (status?.analysis_id) metaParts.push(shortDateFromId(status.analysis_id) || status.analysis_id);
    if (metaParts.length) {
      wrap.appendChild(el("div", { className: "sb-job-meta" }, [metaParts.join(" · ")]));
    }

    const bar = el("div", { className: "na-progress-bar sb-job-bar" });
    bar.appendChild(el("div", {
      className: "na-progress-fill",
      style: `width:${progress}%`,
    }));
    wrap.appendChild(bar);

    const text = job?.message || job?.stage || (running ? "Backtest running…" : "Waiting…");
    wrap.appendChild(el("div", { className: "na-progress-text sb-job-text" }, [text]));
    if (showRetained && job?.backtest_id) {
      const actions = el("div", { className: "sb-job-actions" });
      actions.appendChild(el("a", {
        href: `backtest.html?id=${encodeURIComponent(job.backtest_id)}`,
        className: "sb-job-link",
      }, ["Open backtest →"]));
      wrap.appendChild(actions);
    }
    host.appendChild(wrap);
  }

  async function pollSidebarJobWidget() {
    try {
      const status = await fetchJSON("/api/backtests/status").catch(() => ({ running: false }));
      let job = null;
      if (status && status.running && status.job_id) {
        job = await fetchJSON(`/api/backtest-jobs/${encodeURIComponent(status.job_id)}`).catch(() => null);
      } else if (retainedSidebarJob && retainedSidebarJob.expires_at_ms > Date.now()) {
        job = retainedSidebarJob;
      } else {
        retainedSidebarJob = null;
      }
      if (job && job.status === "completed") {
        retainedSidebarJob = {
          ...job,
          expires_at_ms: Date.now() + JOB_DONE_TTL,
        };
      }
      renderGlobalJobWidget(status, job);
      const nextKey = JSON.stringify({
        running: !!status?.running,
        job_id: status?.job_id || null,
        stage: job?.stage || null,
        progress: job?.progress || null,
        status: job?.status || null,
        backtest_id: job?.backtest_id || null,
      });
      if (lastSidebarJobKey && lastSidebarJobKey !== nextKey && !status?.running) {
        await window.refreshSidebar(true);
      }
      lastSidebarJobKey = nextKey;
    } catch (_) {}
  }

  // ── DATA section: recordings → analyses (flat, no backtests here) ──

  function renderDataSection(container, data, active) {
    const collections = data.collections || [];
    const sessions = data.sessions || [];

    if (!collections.length) {
      container.appendChild(el("div", { className: "sb-empty" }, [
        "No data — ",
        el("a", { href: "collector.html" }, ["Start Collector →"]),
      ]));
      return;
    }

    const sorted = [...collections].sort((a, b) => Number(b.t_start_ms || 0) - Number(a.t_start_ms || 0));

    sorted.forEach(rec => {
      const recId = rec.id;
      const collapsed = isCollapsed("rec:" + recId);
      const analyses = analysesForRecording(recId, sessions);
      const duration = rec.t_start_ms && rec.t_end_ms
        ? fmtDuration(Number(rec.t_end_ms) - Number(rec.t_start_ms)) : "—";

      // Recording row
      const recRow = el("div", { className: "sb-item sb-i0" });
      const toggle = el("span", { className: "sb-toggle" + (collapsed ? "" : " open") }, [collapsed ? "▶" : "▼"]);
      toggle.onclick = (e) => { e.stopPropagation(); toggleCollapsed("rec:" + recId); renderSidebarFromCache(); };
      recRow.appendChild(toggle);
      recRow.appendChild(el("a", { href: `recordings.html?id=${encodeURIComponent(recId)}`, title: recId },
        [`${shortDate(rec.t_start_ms)} · ${duration}`]));
      if (active.page === "recordings" && active.id === recId) recRow.classList.add("active");
      const del = el("span", { className: "sb-del", title: "Delete recording" }, ["×"]);
      del.onclick = (e) => { e.stopPropagation(); location.href = `recordings.html?id=${encodeURIComponent(recId)}&confirm_delete=1`; };
      recRow.appendChild(del);
      container.appendChild(recRow);

      if (collapsed) return;

      // Analysis rows — flat, click → quality, small exp link → explorer
      analyses.forEach(session => {
        const sid = session.id;
        const anaRow = el("div", { className: "sb-item sb-i1" });
        anaRow.appendChild(el("a", { href: `quality.html?analysis=${encodeURIComponent(sid)}`, title: sid },
          [sessionLabel(session)]));
        if ((active.page === "explorer" || active.page === "quality") && active.analysis === sid) {
          anaRow.classList.add("active");
        }
        anaRow.appendChild(el("a", {
          className: "sb-ql sb-ql-e",
          href: `explorer.html?analysis=${encodeURIComponent(sid)}`,
          title: "Open Explorer",
        }, ["exp"]));
        container.appendChild(anaRow);
      });

      const addAction = el("div", { className: "sb-action sb-i1" });
      addAction.appendChild(el("a", { href: `recordings.html?id=${encodeURIComponent(recId)}&action=analyze`,
        style: "color:inherit;text-decoration:none" }, ["+ Analyze"]));
      container.appendChild(addAction);
    });
  }

  // ── RESEARCH section: strategies → backtests → paper ──

  function renderResearchSection(container, data, active) {
    const strategies = data.strategies || [];
    const backtests = data.backtests || [];
    const notebooks = data.notebooks || [];
    const paperRunning = !!(data.paperStatus && data.paperStatus.running);
    const paperStrategyName = data.paperStatus && data.paperStatus.strategy_name;

    if (!strategies.length) {
      container.appendChild(el("div", { className: "sb-empty" }, [
        "No strategies — ",
        el("a", { href: jupyterLabUrl(), target: "_blank" }, ["Open Jupyter ↗"]),
      ]));
      return;
    }

    // Sort alphabetically
    const sorted = [...strategies].sort((a, b) => a.name.localeCompare(b.name));

    sorted.forEach(strat => {
      const name = strat.name;
      const collapsed = isCollapsed("strat:" + name);
      const nbExists = hasNotebook(name, notebooks);
      const btForStrat = backtestsForStrategy(name, backtests);
      const isPaperLive = paperRunning && paperStrategyName === name;

      // Strategy row
      const stratRow = el("div", { className: "sb-item sb-i0" });
      const toggle = el("span", { className: "sb-toggle" + (collapsed ? "" : " open") }, [collapsed ? "▶" : "▼"]);
      toggle.onclick = (e) => { e.stopPropagation(); toggleCollapsed("strat:" + name); renderSidebarFromCache(); };
      stratRow.appendChild(toggle);
      stratRow.appendChild(el("a", { href: `strategy.html?strategy=${encodeURIComponent(name)}` }, [name]));

      // Notebook badge
      const nbBadge = el("span", {
        className: "sb-badge " + (nbExists ? "green" : "yellow"),
        title: nbExists ? "Notebook exists" : "Notebook file missing",
      }, [nbExists ? "nb" : "nb!"]);
      stratRow.appendChild(nbBadge);

      // Active strategy
      if (active.page === "strategy" && active.strategy === name) {
        stratRow.classList.add("active");
      }

      // Delete strategy
      const del = el("span", { className: "sb-del", title: "Delete strategy" }, ["×"]);
      del.onclick = (e) => { e.stopPropagation(); location.href = `strategy.html?strategy=${encodeURIComponent(name)}&confirm_delete=1`; };
      stratRow.appendChild(del);
      container.appendChild(stratRow);

      if (collapsed) return;

      // Backtests: show trades count + pnl
      btForStrat.forEach(bt => {
        const pnl = Number(bt.total_net_pnl_bps);
        const pnlOk = Number.isFinite(pnl);
        const cls = pnlOk && pnl > 0 ? "pos" : pnlOk && pnl < 0 ? "neg" : "";
        const nTr = bt.n_trades != null ? bt.n_trades : "?";
        const pnlStr = pnlOk ? `${signed(pnl)}bps` : "—";
        const btRow = el("div", { className: "sb-item sb-i1" });
        const btLink = el("a", { className: `sb-bt ${cls}`, href: `backtest.html?id=${encodeURIComponent(bt.id)}`, title: bt.id },
          [`${nTr}tr · ${pnlStr}`]);
        btRow.appendChild(btLink);
        if (active.page === "backtest" && active.id === bt.id) btRow.classList.add("active");
        container.appendChild(btRow);
      });

      // Paper — only when live
      if (isPaperLive) {
        const paperRow = el("div", { className: "sb-item sb-i1" });
        paperRow.appendChild(el("span", { className: "sb-live" }));
        paperRow.appendChild(el("a", {
          href: `paper.html?strategy=${encodeURIComponent(name)}`,
          style: "color:#3fb950;text-decoration:none;font-size:10px",
        }, [" paper live"]));
        container.appendChild(paperRow);
      }
    });
  }

  // ── Render from cache (for toggle without re-fetch) ──

  function renderSidebarFromCache() {
    try {
      const cached = sessionStorage.getItem(CACHE_KEY);
      if (cached) {
        const parsed = JSON.parse(cached);
        renderSidebar(parsed.data);
      }
    } catch {}
  }

  // ── Public API ──

  // Insert (or replace) a page-title strip at the top of <main>.
  // nameHtml  — bold entity label, may contain HTML
  // metaText  — plain secondary info (·-separated)
  // actionsHtml — right-side action links/buttons HTML
  window.insertPageTitle = function(nameHtml, metaText, actionsHtml) {
    const existing = document.getElementById("pageTitle");
    if (existing) existing.remove();
    const div = document.createElement("div");
    div.id = "pageTitle";
    div.className = "page-title";
    let html = `<span class="page-title-name">${nameHtml}</span>`;
    if (metaText) html += ` <span class="page-title-meta">${metaText}</span>`;
    if (actionsHtml) html += `<div class="page-title-actions">${actionsHtml}</div>`;
    div.innerHTML = html;
    const main = document.querySelector("main");
    if (main) main.insertBefore(div, main.firstChild);
  };

  window.refreshSidebar = async function(forceFresh) {
    const data = await loadSidebarData(!!forceFresh);
    renderSidebar(data);
  };

  // ── Init ──

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initSidebar);
  } else {
    initSidebar();
  }

  async function initSidebar() {
    bootstrap();
    try {
      const data = await loadSidebarData(false);
      renderSidebar(data);
      if (data.backtestJob && data.backtestJob.status === "completed") {
        retainedSidebarJob = {
          ...data.backtestJob,
          expires_at_ms: Date.now() + JOB_DONE_TTL,
        };
      }
      lastSidebarJobKey = JSON.stringify({
        running: !!data.backtestStatus?.running,
        job_id: data.backtestStatus?.job_id || null,
        stage: (data.backtestJob || retainedSidebarJob)?.stage || null,
        progress: (data.backtestJob || retainedSidebarJob)?.progress || null,
        status: (data.backtestJob || retainedSidebarJob)?.status || null,
        backtest_id: (data.backtestJob || retainedSidebarJob)?.backtest_id || null,
      });
      if (sidebarJobPoll) clearInterval(sidebarJobPoll);
      sidebarJobPoll = window.setInterval(pollSidebarJobWidget, 3000);
    } catch (err) {
      const aside = document.getElementById("sidebar");
      if (aside) aside.innerHTML = `<div style="padding:10px;color:#f85149;font-size:11px">Sidebar error: ${err.message}</div>`;
    }
  }

})();
