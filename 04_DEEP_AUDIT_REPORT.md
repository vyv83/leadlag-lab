# Independent Deep Audit — leadlag-lab

**Date:** 2026-04-17  
**Auditor:** Independent AI agent (Claude Opus 4.6)  
**Scope:** Full-stack audit of leadlag crypto trading platform  
**Method:** Source code review, API contract testing (FastAPI TestClient), data file inspection, status file verification, test suite execution, calculation verification  

---

## Executive Summary

**Overall risk level: HIGH — product is NOT safe for decision-making.**

The application has a functional scaffold with most backend modules in place, but the user's main workflow is broken in 4+ places. Critical calculations have bugs. The UI is engineer-focused (raw tables) not trader-focused (decisions). Real-data verification has never been done.

### 10 Most Important Findings

| # | Finding | Severity | Area |
|---|---------|----------|------|
| 1 | **Limit order exit fee uses maker instead of taker** — undercharges fees on all limit trades | P0 | Calculation |
| 2 | **No UI/API path from collected data → analyzed session** — user collects data but can't proceed to Explorer | P0 | Workflow |
| 3 | **Dashboard network chart always shows zero** — `net_down_bps/net_up_bps` vs `net_sent/net_recv` field mismatch | P0 | Dashboard |
| 4 | **Collector status file goes stale** — says `running: true` 3+ hours after last update, no TTL check | P0 | Ops |
| 5 | **Aster Perp shows status=ok, uptime=100% with zero ticks** — misleading venue health | P0 | Collector |
| 6 | **Collector UI sends `bin_size_ms`/`rotation_s` but backend ignores them** — user thinks they configure, but nothing happens | P0 | API |
| 7 | **Monte Carlo `trade_shuffle` is degenerate for ≤2 trades** — p-value=1.0, looks like no edge | P1 | Calculation |
| 8 | **Paper trader cannot detect Signal C** — realtime detector only emits Signal A | P1 | Paper |
| 9 | **Paper trader IPC with collector is pending** — paper spawns own WS, no shared data | P1 | Paper |
| 10 | **Explorer follower dropdown acts as default filter** — hides events that don't lag the selected follower | P1 | Explorer |

**Is the app safe to use for decision-making right now?** NO.
- Backtest limit fee is wrong (undercharges).
- Monte Carlo can give degenerate results for small trade counts.
- Collector status can mislead about liveness.
- No analyzed sessions exist — Explorer/Backtest screens are empty.
- Paper trading doesn't replicate backtest Signal C.

---

## New P0 Findings

### P0-1: Limit Order Exit Fee Uses Maker Instead of Taker

- **Severity:** P0
- **Area:** Backtest Engine — Calculation
- **Evidence:** `leadlag/backtest/engine.py:419`
- **What happens:** `fee_exit = maker if is_limit else taker`. For limit entry trades, the exit fee is charged as `maker` instead of `taker`. The code comment on line 8 says "Fees: limit = maker+taker (close at market)" but the code gives maker+maker.
- **Why it matters:** Limit trades appear more profitable than they actually are. All limit-order backtest results undercharge exit fees by (taker - maker) bps per trade. For OKX that's 3 bps per trade, for Binance Spot it's 4 bps.
- **How to verify:**
  ```python
  # engine.py:419
  fee_exit = maker if is_limit else taker  # BUG: should always be taker for exit
  ```
- **Suggested fix:** Change line 419 to `fee_exit = taker` (exit is always at market).
- **Acceptance check:** All limit-trade backtest results should have `fee_type_exit = "taker"` and `fee_exit_bps = taker_fee_bps`.

### P0-2: No UI/API Path From Raw Data to Analyzed Session

- **Severity:** P0
- **Area:** Workflow — Core Path
- **Evidence:** `data/sessions/` directory does not exist. `data/ticks/` and `data/bbo/` contain collected parquet files. No `POST /api/sessions/analyze` endpoint exists in `leadlag/api/app.py`.
- **What happens:** User collects data via Collector. Data sits in `data/ticks/` and `data/bbo/`. There is no button, API endpoint, or UI path to turn this raw data into an analyzed session. Explorer shows "No analyzed sessions yet."
- **Why it matters:** The main workflow (collect → analyze → explore → backtest) is broken at step 2. The entire Explorer, Backtest, Quality, and Strategy screens are useless without sessions.
- **How to reproduce:** Start the app, collect data, navigate to Explorer — empty.
- **Suggested fix:** Add `POST /api/sessions/analyze` endpoint that calls `Session.build_from_raw()` and a "Run Analysis" button on Dashboard.
- **Acceptance check:** User clicks "Run Analysis", session appears in Explorer within 30s.

### P0-3: Dashboard Network Chart Always Shows Zero

- **Severity:** P0
- **Area:** Dashboard — Graph
- **Evidence:** `leadlag/ui/dashboard.html:134` reads `r.net_down_bps` and `r.net_up_bps`. `leadlag/monitor/daemon.py:58` writes `net_sent` and `net_recv` (raw byte counts, not bps).
- **What happens:** Network chart renders two flat lines at zero because the JS field names don't match the data written by the monitor daemon.
- **Why it matters:** Dashboard system health section looks broken. User can't assess network bandwidth usage.
- **How to verify:**
  ```python
  import json
  d = json.loads(open('data/.system_history.jsonl').readlines()[-1])
  print(sorted(d.keys()))  # ['cpu_pct', 'disk_used_gb', 'net_recv', 'net_sent', 'ram_used_gb', 'ts']
  # Dashboard expects: net_down_bps, net_up_bps — NOT PRESENT
  ```
- **Suggested fix:** Either rename fields in daemon to `net_down_bps`/`net_up_bps` and compute delta/interval, or change JS to read `net_recv`/`net_sent`.
- **Acceptance check:** Network chart shows non-zero lines correlated with WS traffic.

### P0-4: Collector Status File Stale Without TTL Check

- **Severity:** P0
- **Area:** Operations — Status
- **Evidence:** `data/.collector_status.json` — `running: true`, `updated_at_utc: 2026-04-17T13:09:53`, current time 2026-04-17T16:20. API `read_collector_status()` at `leadlag/monitor/snapshot.py:76-83` reads file without any freshness check.
- **What happens:** `.collector_status.json` says `running: true` but the collector process may have died 3 hours ago. The API adds `proc_alive` field from in-memory `COLLECTOR_PROC`, but after API restart this is always `None`/`False`. Dashboard shows "Collector: running" when it's actually dead.
- **Why it matters:** User sees green status, thinks collector is running, doesn't restart it. Data collection stops silently.
- **How to verify:** `curl localhost:8899/api/collector/status` → `{"running": true, "proc_alive": false}`.
- **Suggested fix:** Add TTL check: if `updated_at_ms` is >120s old, override `running` to `false` and add `stale: true` flag.
- **Acceptance check:** If collector dies, dashboard shows "stopped" or "stale" within 2 minutes.

### P0-5: Aster Perp Shows status=ok, uptime=100% With Zero Ticks

- **Severity:** P0
- **Area:** Collector — Venue Status
- **Evidence:** `data/.collector_status.json` — Aster Perp: `ticks: 0, bbo: 0, status: "ok", uptime_pct: 100.0, bbo_available: true`.
- **What happens:** Venue is connected (WS open) but receives zero data. Status shows "ok" because there are no errors. User sees a healthy venue that contributes nothing.
- **Why it matters:** Analysis on this venue will produce empty/zero results. Strategy that includes Aster will skip all trades there. Quality page may not flag this properly.
- **Suggested fix:** If `ticks == 0 && seconds_since_last_tick == null` after >60s of uptime, status should be `"connected_no_data"` or `"warning"`.
- **Acceptance check:** Aster shows warning/yellow in venue table, not green "ok".

### P0-6: Collector UI Sends bin_size_ms and rotation_s That Backend Ignores

- **Severity:** P0
- **Area:** Collector — API Contract
- **Evidence:** `leadlag/ui/collector.html:186-189` sends `bin_size_ms` and `rotation_s` in POST body. `leadlag/api/app.py:343-353` (`api_collector_start`) only reads `duration_s` and `venues` — ignores `bin_size_ms` and `rotation_s` entirely.
- **What happens:** User adjusts bin size and rotation period in the UI, clicks Start, and the collector runs with hardcoded defaults. User thinks they configured the collection but the parameters are silently dropped.
- **Why it matters:** User can't control bin size or file rotation from the UI. The UI controls are actively misleading.
- **Suggested fix:** Either pass `--bin-size` and `--rotation` to collector subprocess, or remove the controls from the UI.
- **Acceptance check:** Changing bin size in UI results in collector using that bin size, or controls are removed.

### P0-7: Strategy Page Shows Placeholder "scan in Strategies" Instead of Count

- **Severity:** P0
- **Area:** Dashboard — Display
- **Evidence:** `leadlag/ui/dashboard.html:108` — `["Strategies", "scan in Strategies"]`
- **What happens:** Dashboard top card for Strategies shows hardcoded text "scan in Strategies" instead of the actual count. All other cards show real data.
- **Why it matters:** Dashboard looks unfinished. User doesn't know how many strategies exist.
- **Suggested fix:** Fetch `/api/strategies` and show count like sessions/backtests.
- **Acceptance check:** Card shows "N strategies" or "0 — create one".

---

## New P1 Findings

### P1-1: Monte Carlo trade_shuffle Is Degenerate for Small Trade Counts

- **Severity:** P1
- **Area:** Monte Carlo — Calculation
- **Evidence:** `leadlag/montecarlo.py:117-118` — `return np.array([rng.permutation(returns) for _ in range(n)])`. Verified: with 1 trade, all simulations are identical → p_value=1.0.
- **What happens:** For ≤3 trades, shuffling produces very few unique permutations. The p-value becomes meaningless (1.0 or very coarse). User sees "p-value: 100%" and concludes strategy has no edge, when actually there's just too little data.
- **Why it matters:** User makes wrong robustness conclusion from degenerate Monte Carlo.
- **Suggested fix:** Show warning when n_trades < 20. Suggest `block_bootstrap` for small samples. Add explanation card.
- **Acceptance check:** Monte Carlo page shows "⚠ Too few trades for reliable shuffle test" when n < 20.

### P1-2: Paper Trader Cannot Detect Signal C (Only Signal A)

- **Severity:** P1
- **Area:** Paper Trading — Realtime
- **Evidence:** `leadlag/realtime/detector.py:77` — `signal="A"` hardcoded. Comment says "A/B/C classification is a batch concept."
- **What happens:** Realtime detector always emits Signal A regardless of whether both leaders confirm. Strategies that trade on Signal C only will never fire in paper trading.
- **Why it matters:** Paper trading results won't match backtest results for Signal C strategies. This invalidates the backtest → paper → live workflow.
- **Suggested fix:** Implement Signal B/C detection in RealtimeDetector (track both leaders, emit C when both cross).
- **Acceptance check:** Paper trader on same data produces Signal C events that match batch detection.

### P1-3: Paper Trader IPC With Collector Is Pending

- **Severity:** P1
- **Area:** Paper Trading — Architecture
- **Evidence:** `leadlag/paper/__main__.py` contains `collector_ipc_pending` references. Paper trader spawns its own WS connections.
- **What happens:** When collector is already running, paper trader creates duplicate WS connections to all venues. This doubles bandwidth and can cause exchange rate limits.
- **Why it matters:** Paper trading can't coexist safely with collector. Also loses tick-for-tick parity with collected data.
- **Suggested fix:** Implement Unix socket or shared queue for collector → paper tick forwarding.
- **Acceptance check:** Paper trader reads ticks from running collector without opening new WS connections.

### P1-4: Explorer Follower Dropdown Acts as Event Filter

- **Severity:** P1
- **Area:** Explorer — UX
- **Evidence:** `leadlag/ui/explorer.html:158` — `if (follower && !(e.lagging_followers || []).includes(follower)) return false;`
- **What happens:** Selecting a follower in the dropdown hides all events where that follower is NOT lagging. This feels like a display selector ("show this venue's chart") but actually filters the event list. User can lose 80% of events by selecting a follower.
- **Why it matters:** User selects a follower to see its chart, doesn't realize events disappeared. Makes wrong conclusions about event count and signal distribution.
- **Suggested fix:** Separate "chart follower" (display-only) from "filter by follower" (checkbox/toggle).
- **Acceptance check:** Changing follower dropdown updates the chart but doesn't reduce event count unless explicit "filter" checkbox is checked.

### P1-5: Explorer Reset Filters Does Not Reset Follower

- **Severity:** P1
- **Area:** Explorer — UX
- **Evidence:** `leadlag/ui/explorer.html:396-402` — Reset button clears `leaderMode, direction, minMag, minLagging, timeFrom, timeTo, sortBy` but NOT `follower`.
- **What happens:** User clicks "Reset Filters", expects all filters cleared. But follower dropdown retains its value, continuing to hide events.
- **Why it matters:** User thinks they see all events after reset, but follower filter is still active.
- **Suggested fix:** Add `document.getElementById("follower").value = meta.followers[0] || "";` to reset handler, or show all events when no explicit filter.
- **Acceptance check:** After clicking Reset, event count matches "All" signal button count.

### P1-6: Explorer OKX/Bybit Leader Filter Includes Confirmed Events Incorrectly

- **Severity:** P1
- **Area:** Explorer — Filter Logic
- **Evidence:** `leadlag/ui/explorer.html:160-161`:
  ```javascript
  if (leaderMode === "okx" && !["OKX Perp", "confirmed"].includes(e.leader) && e.anchor_leader !== "OKX Perp") return false;
  ```
- **What happens:** When filtering "OKX only", events with `leader: "confirmed"` (Signal C) pass through even though they may have been anchored by Bybit, not OKX. The `anchor_leader` check catches some but the `leader === "confirmed"` bypass lets them through first.
- **Why it matters:** "OKX only" shows Signal C events that were actually Bybit-anchored. Misleading signal attribution.
- **Suggested fix:** Remove `"confirmed"` from the includes check. Only check `anchor_leader`.
- **Acceptance check:** "OKX only" filter shows only events where OKX was the anchor leader.

### P1-7: Explorer Keyboard Navigation Conflicts With Input Fields

- **Severity:** P1
- **Area:** Explorer — UX
- **Evidence:** `leadlag/ui/explorer.html:403-406`:
  ```javascript
  document.addEventListener("keydown", ev => {
    if (["ArrowDown", "ArrowRight"].includes(ev.key)) moveEvent(1);
    if (["ArrowUp", "ArrowLeft"].includes(ev.key)) moveEvent(-1);
  });
  ```
- **What happens:** Arrow keys navigate events even when user is typing in a number input (Min σ, Min lagging) or time input. Pressing Up/Down in the magnitude input simultaneously changes the event selection.
- **Why it matters:** Editing filter values triggers event navigation. Frustrating UX.
- **Suggested fix:** Check `ev.target.tagName !== "INPUT" && ev.target.tagName !== "SELECT"` before navigating.
- **Acceptance check:** Arrow keys in input fields don't change selected event.

### P1-8: Backtest Reverse Mode May Drop the Close Trade

- **Severity:** P1
- **Area:** Backtest Engine — Position Mode
- **Evidence:** `leadlag/backtest/engine.py:186-193`:
  ```python
  if position_mode == "reverse":
      same_dir = any(p["side"] == order.side for p in open_on_venue)
      if same_dir:
          n_skipped_position += 1
          continue
      open_positions[order.venue] = []  # Clear but DON'T close
  ```
- **What happens:** In reverse mode, when a new signal comes in the opposite direction, existing positions are silently cleared (`= []`) without generating close trades. The PnL of the cleared position is never recorded.
- **Why it matters:** Equity curve misses the close leg of reversed positions. Total PnL is wrong.
- **Suggested fix:** Generate a close trade for each cleared position before opening the reverse.
- **Acceptance check:** Every opened position has a corresponding close trade in trades.json.

### P1-9: Navigation Menus Are Inconsistent Across Pages

- **Severity:** P1
- **Area:** UI/UX — Navigation
- **Evidence:** Comparing nav sections across all HTML files:

| Page | Dashboard | Collector | Explorer | Quality | Strategies | Backtests | MC | Paper | Trade |
|------|-----------|-----------|----------|---------|------------|-----------|-----|-------|-------|
| dashboard.html | ✓ | ✓ | ��� | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| collector.html | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| explorer.html | �� | ✗ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| strategy.html | ✓ | ✗ | ✓ | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| backtest.html | ✓ | ✗ | ✓ | ✗ | ✓ | ✓ | ✓ | ✗ | ✗ |
| trade.html | ✓ | ✗ | ✓ | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| montecarlo.html | ��� | ✗ | ✓ | ✗ | ✓ | ✓ | ✓ | ✗ | ✗ |
| paper.html | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ | ✗ | ✓ | ✗ |
| quality.html | �� | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |

- **What happens:** Users can't navigate between all pages from every page. Paper is missing from most navs. Monte Carlo is missing from 5 pages. Trade Inspector has no nav entry.
- **Why it matters:** Navigation feels incomplete and inconsistent. User gets "stuck" on pages with limited nav.
- **Suggested fix:** Standardize nav across all pages. Include all 9 page links everywhere.
- **Acceptance check:** Every page has the same nav bar with all links.

### P1-10: Monte Carlo Run Button Not Disabled During Execution

- **Severity:** P1
- **Area:** Monte Carlo — UX
- **Evidence:** `leadlag/ui/montecarlo.html:102-115` — `runMonteCarlo()` sets status text but doesn't disable the Run button.
- **What happens:** User clicks Run, waits 5-30 seconds. Button is still clickable. User clicks again, queuing a second run.
- **Why it matters:** Multiple simultaneous Monte Carlo runs could crash the browser (each generates 10K equity curves) or produce corrupt results.
- **Suggested fix:** Disable Run button during execution, re-enable on complete/error.
- **Acceptance check:** Run button shows "Running..." and is disabled while Monte Carlo executes.

### P1-11: Jupyter Link Hardcoded to 127.0.0.1:8888

- **Severity:** P1
- **Area:** Dashboard — Link
- **Evidence:** `leadlag/ui/dashboard.html:53` — `<a class="button-link" href="http://127.0.0.1:8888" target="_blank">Open Jupyter</a>`
- **What happens:** Jupyter link points to hardcoded localhost:8888. If Jupyter runs on a different port, behind nginx, or isn't running at all, link is broken.
- **Why it matters:** Key workflow (Jupyter as the "lab") is broken from the very first click.
- **Suggested fix:** Make Jupyter URL configurable or auto-detect from API.
- **Acceptance check:** Jupyter link opens correct Jupyter instance, or shows "Jupyter not running" message.

### P1-12: No Active Menu Item Indication

- **Severity:** P1
- **Area:** UI/UX — Navigation
- **Evidence:** `leadlag/ui/style.css` — No `.active` class for nav links. All nav links look identical.
- **What happens:** User can't tell which page they're on from the nav bar.
- **Why it matters:** Confusing navigation, especially on similar-looking pages (Explorer vs Backtest).
- **Suggested fix:** Add CSS for `nav a.active` or `nav a[aria-current="page"]` and set it per page.
- **Acceptance check:** Current page's nav link is visually distinct (different color, underline, or background).

---

## P2 / Polish Findings

| # | Finding | Area |
|---|---------|------|
| P2-1 | No empty state guidance — Explorer shows "No analyzed sessions yet" with no "Create Session" CTA | Explorer |
| P2-2 | Strategy page params shown as raw JSON string — not user-readable | Strategy |
| P2-3 | Strategy run error shows raw JSON `<pre>` block instead of readable error | Strategy |
| P2-4 | Backtest trade table has 23 columns — too wide, needs horizontal scroll on most screens | Backtest |
| P2-5 | Trade Inspector SL/TP are label-only annotations, not horizontal lines on chart | Trade |
| P2-6 | Trade Inspector MFE/MAE annotations overlap at same x position as ENTRY | Trade |
| P2-7 | Quality "Export report" exports raw JSON, not human-readable format | Quality |
| P2-8 | Quality bar chart colors: all negative values are red regardless of metric semantics | Quality |
| P2-9 | Paper trades table shows last 80 trades without pagination | Paper |
| P2-10 | No tooltips or help text on any control across the entire app | Global |
| P2-11 | No responsive design below 980px except basic grid collapse | Global |
| P2-12 | Auto-refresh every 5s causes DOM rebuilds (fillCards/fillTable) with potential flicker | Global |
| P2-13 | No "last updated" timestamp visible on auto-refreshing pages | Global |
| P2-14 | collector.html restart doesn't pass bin_size_ms/rotation_s (inconsistent with start) | Collector |
| P2-15 | `fmt()` returns "—" but some places use "N/A" for null — inconsistent null display | Global |

---

## Screen-by-Screen UI/UX Review

### Dashboard

**What is broken:**
- Network chart always shows zero (field name mismatch P0-3)
- Strategies card shows "scan in Strategies" placeholder (P0-7)
- Collector status stale after API restart (P0-4)

**What is misleading:**
- Collector shows "running" when process died hours ago
- Net recv/sent shows raw bytes (e.g., "1234567890") with no units label — is this bytes? KB? MB?

**What is incomplete:**
- No "Run Analysis" button to process raw data into sessions
- No process health indicators (CPU/memory per process)
- No next-action guidance ("Collect data → Analyze → Explore → Backtest")

**What is inconvenient:**
- 9 API calls fire on every 5s refresh — heavy for a dashboard
- Open Latest Session points to empty Explorer when no sessions exist
- No ability to configure collector duration from dashboard (redirects to Collector page)

**Fix before Flutter:**
- Fix network chart fields
- Fix strategy card placeholder
- Add collector TTL check
- Add "Run Analysis" workflow

**Can wait for Flutter:**
- Per-process monitoring
- Sparkline charts in cards
- Next-action guidance

### Collector

**What is broken:**
- `bin_size_ms` and `rotation_s` controls are ignored by backend (P0-6)
- Restart button drops bin_size_ms/rotation_s parameters

**What is misleading:**
- Aster Perp: 0 ticks, status "ok", uptime 100% (P0-5)
- `ticks_per_s_1m` and `ticks_per_s_10m` show identical values (both use same field from status file)
- `median_price` is actually `last_price` (status file uses `last_price` for both)

**What is incomplete:**
- Log viewer has no pagination — loads entire .jsonl file
- No "connected but no data" warning per venue
- No auto-reconnect indicator beyond reconnect count
- No estimate of remaining collection time

**What is inconvenient:**
- WS URLs are very long and make the venue table hard to read (toggleable but defaults to showing)
- 16 columns in live monitor table — overwhelming
- No venue grouping (leaders vs followers visual separation)

**Fix before Flutter:**
- Remove or wire bin_size_ms/rotation_s
- Add "no data" warning for venues with 0 ticks after 60s
- Fix restart to pass all parameters
- Fix median_price vs last_price display

**Can wait for Flutter:**
- Log pagination
- Venue grouping
- Remaining time estimate

### Explorer

**What is broken:**
- Follower dropdown acts as event filter (P1-4)
- Reset filters doesn't reset follower (P1-5)
- OKX/Bybit filter includes confirmed events incorrectly (P1-6)
- Keyboard nav conflicts with input fields (P1-7)

**What is misleading:**
- Event count changes when selecting follower (looks like a display bug, is actually a filter)
- "Confirmed only" leader filter works differently from "OKX only" / "Bybit only"

**What is incomplete:**
- No pagination for events table (all events in DOM at once)
- No "why is this event important?" explanation
- Follower table "Net 2s/5s/10s/30s" column names are unclear (what units? what do they mean?)
- URL params don't fully restore state (follower, sort, showAllFollowers not synced)

**What is inconvenient:**
- Event table is fixed-width (360px min) — on small screens, chart gets squished
- No way to compare two events side by side
- Selecting an event requires click — no detail preview on hover
- Many events have identical magnitude — hard to distinguish

**Fix before Flutter:**
- Separate follower chart selector from event filter
- Fix Reset to include follower
- Fix leader filter logic
- Fix keyboard nav in inputs
- Add URL sync for all filter state

**Can wait for Flutter:**
- Pagination
- Event comparison
- Hover preview

### Strategy

**What is broken:**
- Nothing technically broken, but critically incomplete

**What is misleading:**
- Strategy params shown as raw JSON — user can't read `{"hold_ms": 30000, "slippage_model": "half_spread"}`
- `params_override` input is raw JSON — scary for non-developers

**What is incomplete:**
- No strategy creation UI
- No strategy source code viewer
- No strategy validation before run
- No loading indicator during backtest run
- No last backtest summary per strategy
- No link to Jupyter for editing
- Run button doesn't disable during execution
- Error display is raw JSON `<pre>` block

**Fix before Flutter:**
- Add loading/disabled state on Run
- Show readable params (key-value table instead of JSON)
- Add basic empty state with "Create strategy in Jupyter" guidance
- Show human-readable error messages

**Can wait for Flutter:**
- Source code editor
- Strategy creation wizard
- Validation UI

### Backtest

**What is broken:**
- Layer toggles work but don't affect the chart title/legend clarity

**What is misleading:**
- "Post Fee" layer name is "Gross - Fees" but doesn't include slippage — unclear
- Drawdown subplot title says "drawdown bps" but values are negative (expected but confusing)
- Equity chart click navigates to trade — no hover indicator that clicking is possible

**What is incomplete:**
- 23-column trade table is very wide — no column visibility toggle
- No CSV export (only JSON)
- No pagination on trade table
- No trade summary statistics per filtered set (only for full set)
- Spread filter buckets don't match backtest engine spread buckets exactly

**What is inconvenient:**
- Distribution charts (PnL hist, hold hist, scatter) all show full dataset regardless of trade filter
- No way to compare two backtests
- No "this backtest is profitable/unprofitable" verdict card
- Fee/slippage impact table shows absolute values — hard to interpret without context

**Fix before Flutter:**
- Add column visibility toggle for trade table
- Sync distribution charts with trade filters
- Add verdict card ("profitable after fees" / "unprofitable")
- Add CSV export

**Can wait for Flutter:**
- Backtest comparison
- Pagination
- Advanced column management

### Trade Inspector

**What is broken:**
- SL/TP shown as text annotations only, not as horizontal lines (plan says "lines not labels")
- MFE/MAE annotations at same x position as ENTRY — overlap and are unreadable

**What is misleading:**
- MFE shown as "±X bps @ 0 ms" when MFE never occurred (0 is the default, not meaningful)
- "Spread entry: N/A" doesn't explain WHY it's N/A (BBO unavailable? venue without BBO?)

**What is incomplete:**
- No "why did this trade win/lose?" analysis
- No BBO at entry/exit snapshot comparison
- Prev/Next work correctly but no keyboard shortcuts

**Fix before Flutter:**
- SL/TP as horizontal lines
- Offset MFE/MAE annotations to avoid overlap
- Show "MFE: —" instead of "MFE: +0.00 bps @ 0 ms" when no MFE recorded

**Can wait for Flutter:**
- Trade analysis ("lost because spread > PnL")
- Keyboard shortcuts for prev/next

### Monte Carlo

**What is broken:**
- Run button not disabled during execution (P1-10)
- Degenerate results for small trade counts (P1-1)

**What is misleading:**
- p-value labeled as "p-value" but displayed as percent — "100%" looks good, is actually terrible
- No explanation of what p-value means in this context
- "Block size" input visible for all methods but only relevant for block_bootstrap
- Default method "trade_shuffle" — no guidance on when to use which

**What is incomplete:**
- No "real vs simulated" comparison line on Sharpe and Drawdown histograms (only on Final PnL)
- No warning for degenerate results
- No cancel button for long-running simulation
- 10,000 × equity curve data sent in single JSON response — potential browser freeze

**Fix before Flutter:**
- Add method description / contextual help
- Hide block_size when not using block_bootstrap
- Add real-value marker line on all histograms
- Show warning when n_trades < 20
- Disable Run during execution

**Can wait for Flutter:**
- Cancel button
- Streaming results
- Method auto-selection

### Paper

**What is broken:**
- Paper can't trade Signal C (P1-2)
- Paper IPC pending (P1-3)
- Venue connectivity table shows static config data, not real-time status

**What is misleading:**
- "Venue Connectivity" table shows venues from config, not actual connected venues
- Status shows `running: false` when paper hasn't been started, same as when it's been stopped — can't tell difference

**What is incomplete:**
- No link to related backtest for comparison
- No "backtest vs paper" overlay chart
- No blocked state indicator (when collector IPC is pending)
- Equity chart shows only "No closed paper trades yet" — no explanation of what to expect

**Fix before Flutter:**
- Implement Signal C in realtime detector
- Implement IPC or clearly show "No collector running" state
- Add "Start collector first" guidance

**Can wait for Flutter:**
- Backtest comparison overlay
- Real venue connectivity

### Quality

**What is broken:**
- Nothing technically broken

**What is misleading:**
- Bar chart colors: negative price deviation shows red, but negative deviation might be normal
- "Flags" section shows count only, no severity explanation
- Timeline gaps table doesn't correlate with charts

**What is incomplete:**
- No "recompute" button
- No timeline visualization of gaps (only table)
- No severity explanation for flag reasons
- Export is raw JSON only
- No per-venue recommendation ("skip Aster", "edgeX marginal")

**Fix before Flutter:**
- Add severity explanation tooltips for flag reasons
- Add "Data suitable for trading" / "Research only" verdict
- Fix bar chart color semantics

**Can wait for Flutter:**
- Timeline gap visualization
- Per-venue recommendations
- CSV/PDF export

---

## Incorrect or Misleading Data Display

| # | Location | What's shown | What's wrong | Severity |
|---|----------|-------------|-------------|----------|
| 1 | Dashboard → Network chart | Two zero lines | Fields don't match (`net_down_bps` vs `net_sent`) | P0 |
| 2 | Dashboard → Strategies card | "scan in Strategies" | Hardcoded placeholder, not real count | P0 |
| 3 | Dashboard → Collector status | "running" | Stale status file, process may be dead | P0 |
| 4 | Dashboard → Net recv/sent | Raw byte count "1234567890" | No units label (bytes? KB? MB?) | P1 |
| 5 | Collector → Aster Perp | status "ok", uptime 100% | Zero ticks, zero BBO — effectively dead | P0 |
| 6 | Collector → ticks/s 1m vs 10m | Identical values | Both populated from same field in status | P1 |
| 7 | Collector → median price | Shows last price | Status file stores `median_price` = last price snapshot, not rolling median | P1 |
| 8 | Explorer → event count after follower select | Reduced count | Follower acts as filter, not display selector | P1 |
| 9 | Backtest → "Gross - Fees" label | Implies fee-adjusted | Doesn't include slippage; name is ambiguous | P2 |
| 10 | Trade → MFE "0 bps @ 0 ms" | Looks like MFE was measured | Default value when MFE never occurred | P2 |
| 11 | Monte Carlo → p-value "100%" | Looks like high confidence | Actually means zero statistical significance | P1 |
| 12 | Paper → Venue status | Config values | Not live connectivity status | P1 |
| 13 | Quality → bar chart red/blue | Red = negative | Negative deviation might be normal, not bad | P2 |

---

## Broken or Weak Graphs

| # | Chart / Page | Data Source | Current Issue | Expected Behavior |
|---|-------------|-------------|---------------|-------------------|
| 1 | Dashboard → netChart | `.system_history.jsonl` → `net_down_bps` | Always zero — field mismatch | Show actual network bytes/s as delta between readings |
| 2 | Explorer → eventChart | `price_window.venues` | BBO fill "tonexty" connects to wrong trace if traces are added in wrong order | BBO bid-ask band should always form a corridor |
| 3 | Trade → tradeChart annotations | Trade entry/exit | ENTRY, SL, TP all at same x — overlap | Stagger y positions or use horizontal lines for SL/TP |
| 4 | Monte Carlo → equityFan | `sim_equity_curves` (up to 1000) | With 10K sims, still renders 1000 semi-transparent lines — can freeze browser | Use percentile bands (5/25/50/75/95) instead of individual lines |
| 5 | Monte Carlo → sharpeHist | `sim_sharpes` | No real-value marker line | Add vertical line at actual Sharpe ratio |
| 6 | Monte Carlo → ddHist | `sim_max_dds` | No real-value marker line | Add vertical line at actual max drawdown |
| 7 | Backtest → equityChart | `equity.json` | Click navigates to trade but no hover indicator | Show cursor:pointer on hover, tooltip with trade summary |
| 8 | Backtest → distributions | `trades` array | Not synced with trade filters | Filter distributions when trade filters change |
| 9 | Quality → charts | Quality metrics per venue | Price deviation chart: red for negative values is incorrect semantics | Color by severity (flag status), not by sign |

---

## Broken or Weak Tables

| # | Table / Page | Missing Columns | Bad Formatting | No Sort/Pagination | Misleading Cells | Action |
|---|-------------|-----------------|----------------|---------------------|------------------|--------|
| 1 | Backtest → trades | — | 23 columns, overflows on most screens | No pagination for 100+ trades | fee column shows "undefined/taker" if fee_type_entry missing | Add column toggle, pagination |
| 2 | Explorer → events | Event explanation | — | No pagination | `#` column is display index, not event_id | Add real event_id, pagination |
| 3 | Explorer → followers | Edge conclusion | Net column headers unclear ("Net 2s" means what?) | — | — | Add tooltips for Net columns |
| 4 | Collector → live | — | 16 columns, very wide | — | ticks/s 1m = ticks/s 10m (identical) | Remove duplicate column |
| 5 | Quality → venues | Severity explanation | 20+ columns, overwhelming | — | Aster shows "good" with 0 ticks | Add inline severity badges |
| 6 | Paper → trades | — | — | Shows last 80, no pagination | — | Add pagination |
| 7 | Paper → signals | Trade link | — | Shows last 40 | Action "skip" has no explanation | Link to related trade, explain skip |
| 8 | Dashboard → sessions | Quality summary | — | Max 8 rows | — | Show quality flag color |
| 9 | Strategy → strategies | Source preview, last backtest | Params as raw JSON | — | — | Format params as key-value |

---

## Backend/API Bugs

| # | Bug | File:Line | Severity | Detail |
|---|-----|-----------|----------|--------|
| 1 | Limit exit fee is maker, should be taker | `engine.py:419` | P0 | `fee_exit = maker if is_limit else taker` — comment says "close at market" |
| 2 | Ignored parameters `bin_size_ms`/`rotation_s` | `app.py:343-353` | P0 | Collector start endpoint reads only `duration_s` and `venues` |
| 3 | Strategy delete has no path validation | `app.py:147-150` | P1 | `name` is user-supplied, used directly in `Path(f"{name}.py")` |
| 4 | Paper trader path has no validation | `app.py:433-434` | P1 | `name` parameter used in `DATA_DIR / "paper" / name` |
| 5 | ContractError returns HTTP 500 | `app.py:244` | P2 | Should be 422 Unprocessable Entity |
| 6 | `type` parameter name shadows builtin | `app.py:333` | P2 | FastAPI parameter named `type` shadows Python builtin |
| 7 | Reverse mode drops positions without close trades | `engine.py:186-193` | P1 | `open_positions[venue] = []` silently discards |
| 8 | Collector status no freshness check | `snapshot.py:76-83` | P0 | Reads stale file without TTL |
| 9 | Paper stop writes `running: false` but doesn't clean trade state | `app.py:414` | P2 | Cumulative PnL and open positions not cleaned |
| 10 | `COLLECTOR_PROC` global lost on API restart | `app.py:33` | P1 | Can't stop a collector started before API restart |

---

## Calculation/Contract Bugs

| # | Bug | File:Line | Severity | Detail |
|---|-----|-----------|----------|--------|
| 1 | Limit exit fee: maker instead of taker | `engine.py:419` | P0 | Undercharges fees by (taker-maker) bps per limit trade |
| 2 | Reverse mode PnL loss | `engine.py:186-193` | P1 | Position cleared without generating close trade |
| 3 | Monte Carlo degenerate for small n | `montecarlo.py:117-118` | P1 | Single-trade shuffle always produces p=1.0 |
| 4 | Realtime only Signal A | `detector.py:77` | P1 | No Signal B/C in paper trading |
| 5 | Grid search fees use registry, not strategy override | `session.py:481-486` | P2 | Grid results may not match backtest with overridden fees |
| 6 | Paper exit slippage sign | `trader.py:221` | Verified OK | `exit_exec = vwap * (1 - sign * slip/1e4)` is mathematically correct |
| 7 | Backtest gross_pnl vs net_pnl formula inconsistency | `engine.py:422-425` | P2 | gross uses vwap prices, net uses exec prices — logically correct but slippage is counted in both price adjustment AND slip_total field, making fields confusing to audit |
| 8 | MFE/MAE baseline is entry_price_exec | `engine.py:397` | OK | Correct: MFE/MAE relative to actual fill price |
| 9 | Paper `n_trades_closed` can go negative | `trader.py:319` | P2 | `self._trade_id - sum(open)` is wrong if trades close out of order |

---

## Tests Missing

### Critical Tests (should exist before any real trading)

| Test Name | Scenario | Why Missing Matters |
|-----------|----------|---------------------|
| `test_limit_exit_fee_is_taker` | Limit order trade should have `fee_type_exit = "taker"` | P0 fee bug undetected |
| `test_reverse_mode_generates_close_trade` | Position reversed → old position has close trade | P1 PnL loss undetected |
| `test_stop_loss_triggers_at_exact_threshold` | pnl = -SL bps → exit_reason = "stop_loss" | No SL testing |
| `test_take_profit_triggers` | pnl = +TP bps → exit_reason = "take_profit" | No TP testing |
| `test_montecarlo_small_n_warning` | 1-3 trades → warning or different method | Degenerate MC undetected |
| `test_collector_status_staleness` | Status file >120s old → running = false | Stale status undetected |
| `test_realtime_signal_c_detection` | Both leaders cross threshold → Signal C | Signal C missing in paper |
| `test_session_build_from_raw_parquet` | Real parquet → session with expected event count | No real data test |
| `test_backtest_zero_trades` | Strategy returns no orders → empty stats, no crash | Edge case untested |
| `test_path_traversal_strategy_delete` | `../../etc/passwd` as name → rejected | Security untested |

### Integration Tests

| Test Name | Scenario |
|-----------|----------|
| `test_collect_analyze_backtest_pipeline` | Raw parquet → session → backtest end-to-end |
| `test_paper_matches_backtest_signals` | Same events produce same signals in batch vs realtime |
| `test_api_collector_start_stop_restart` | Start → verify running → stop → verify stopped → restart |
| `test_all_navigation_links_valid` | Every nav link in every HTML file points to existing page |
| `test_api_response_contracts` | Every API endpoint returns expected field names and types |

### Performance Tests

| Test Name | Scenario |
|-----------|----------|
| `test_explorer_500_events_load_time` | 500 events load in < 2s (plan acceptance criterion) |
| `test_montecarlo_10k_no_browser_freeze` | 10K sims with 100 trades doesn't exceed 200MB response |
| `test_collector_log_large_file` | 1M-line log file doesn't crash API |

---

## Commands Run

| Command | Result |
|---------|--------|
| `pytest tests/ -q` | 13 passed in 2.75s |
| `cat data/.collector_status.json` | running: true (stale 3h+) |
| `ls data/sessions/` | Does not exist |
| `ls data/strategies/` | Does not exist |
| `ls data/backtest/` | Does not exist |
| FastAPI TestClient: `GET /api/collector/status` | `{"running": true, "proc_alive": false}` |
| FastAPI TestClient: `GET /api/sessions` | `[]` (empty) |
| FastAPI TestClient: `GET /api/strategies` | `[]` (empty) |
| FastAPI TestClient: `GET /api/backtests` | `[]` (empty) |
| FastAPI TestClient: `DELETE /api/strategies/../../etc/passwd` | 404 (FastAPI path routing prevents basic traversal) |
| Python verification: exit slippage sign | Mathematically correct |
| Python verification: limit fee exit | BUG confirmed: uses maker instead of taker |
| Python verification: MC single-trade shuffle | BUG confirmed: p_value=1.0, degenerate |
| Python verification: network chart fields | BUG confirmed: `net_down_bps` vs `net_sent` mismatch |
| Python verification: Aster status | BUG confirmed: 0 ticks, status "ok", uptime 100% |

---

## Final Checklist: Add These To P0 Before Flutter

- [ ] **Fix limit exit fee** — `engine.py:419`: change `fee_exit = maker if is_limit else taker` to `fee_exit = taker`
- [ ] **Add `/api/sessions/analyze` endpoint** — unblock collect→analyze→explore workflow
- [ ] **Fix network chart field names** — align daemon output with dashboard JS
- [ ] **Add collector status TTL** — if `updated_at_ms > 120s ago`, set `running: false, stale: true`
- [ ] **Fix Aster venue status** — 0 ticks after 60s = status "connected_no_data", not "ok"
- [ ] **Remove or wire `bin_size_ms`/`rotation_s`** — collector start ignores these UI params
- [ ] **Fix strategy card placeholder** — show actual count instead of "scan in Strategies"
- [ ] **Fix reverse mode** — generate close trades before clearing positions
- [ ] **Separate follower filter from chart display** — Explorer dropdown shouldn't filter events
- [ ] **Fix Explorer Reset** — include follower dropdown in reset
- [ ] **Fix OKX/Bybit filter** — remove `"confirmed"` bypass
- [ ] **Fix keyboard nav** — ignore arrow keys when input/select focused
- [ ] **Standardize navigation** — same nav bar on all 9 pages
- [ ] **Disable Monte Carlo Run button** during execution
- [ ] **Add Monte Carlo small-n warning** — trade_shuffle with <20 trades is degenerate
- [ ] **Fix Jupyter link** — make URL configurable or auto-detect
- [ ] **Add active menu item** CSS for navigation
