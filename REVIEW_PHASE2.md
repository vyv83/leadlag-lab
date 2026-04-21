# Phase 2 Review

Date: 2026-04-21

## Findings

1. Jupyter notebook links were broken.
   `strategy.html` and `backtest.html` linked to the wrong notebook routes. The service uses `base_url=/leadlag-lab/lab/`, and JupyterLab itself adds its own `lab/...` UI route, so notebook links must resolve under `/leadlag-lab/lab/lab/tree/<name>.ipynb`.

2. Sidebar delete affordances did not actually complete the delete flow.
   Sidebar `×` buttons routed to `?confirm_delete=1`, but `recordings.html` and `strategy.html` did not consistently open a visible confirmation state from that query param.

3. Sidebar navigation order did not match the user pipeline.
   `Paper` was shown near the top even though it is the last stage in the workflow.

4. Strategy actions were noisy and low-signal.
   The `Detail` button duplicated row-click behavior and the action area looked like cramped table cells instead of explicit actions.

5. Visual language was too dense.
   The sidebar, action buttons, and delete controls used inconsistent spacing and too many inline styles.

## Fixes Applied

- Added shared Jupyter URL helpers in `leadlag/ui/app.js`.
- Fixed notebook links in `leadlag/ui/strategy.html` and `leadlag/ui/backtest.html`.
- Reordered sidebar primary navigation to: Dashboard → Collector → Recordings → Strategies → Backtests → Monte Carlo → Paper.
- Reworked sidebar section labels, notebook badges, spacing, and footer CTA in `leadlag/ui/sidebar.js` and `leadlag/ui/style.css`.
- Removed the useless `Detail` button from strategies and replaced it with direct high-signal actions.
- Replaced ad-hoc inline danger buttons with reusable button styles in `leadlag/ui/style.css`.
- Added working `confirm_delete` handling for strategy and recording deletion routes.
- Added inline delete confirmation UI for recordings.

## Manual Verification Plan

1. Open a strategy from `strategy.html` and verify `Open Notebook ↗` reaches JupyterLab.
2. Open a backtest and verify `Open Notebook ↗` reaches the strategy notebook.
3. Click sidebar delete on a strategy and verify the confirmation panel opens automatically.
4. Click sidebar delete on a recording and verify the confirmation panel opens automatically.
5. Create a copy of `notebooks/strategy_dev.ipynb`, verify it appears in `/api/notebooks`, then test delete flow on the copy only.

## Verification Performed

- Confirmed from `deploy/leadlag-lab-jupyter.service` and `journalctl` that:
  - `ServerApp.base_url=/leadlag-lab/lab/`
  - JupyterLab UI routes actually live under `/leadlag-lab/lab/lab/...`
  - broken requests were logged as `404 GET /leadlag-lab/lab/tree/strategy_dev.ipynb`
  - so the correct notebook route is `/leadlag-lab/lab/lab/tree/strategy_dev.ipynb`
- Created a real temporary copy:
  - `notebooks/phase2_review_copy_20260421.ipynb`
  - `data/strategies/phase2_review_copy_20260421.py`
- Verified backend visibility before delete:
  - notebook present: `true`
  - strategy present: `true`
- Ran real delete logic as the service user `leadlag-lab`:
  - `delete_strategy("phase2_review_copy_20260421", include_notebook=True)`
  - result: `{"ok": true, "removed_backtests": 0, "notebook_deleted": true}`
- Verified both files were gone after delete:
  - notebook exists after: `false`
  - strategy exists after: `false`
- JS syntax check passed for:
  - `leadlag/ui/app.js`
  - `leadlag/ui/sidebar.js`

## Notes

- `PROGRESS_PHASE2.md` currently overstates completion. This file is the corrective review log for the current stabilization pass.
- The delete smoke-test revealed an ownership nuance: deleting these files from the current shell user can fail with `PermissionError`, while the real app path works under the service user `leadlag-lab`. That is important operational context, but it does not block the actual UI flow when the service is running under the intended account.
