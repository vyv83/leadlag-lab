# LeadLag Lab — Design Context

`register: product`

## Design Intent

LeadLag Lab should feel like a compact technical workstation: calm, dense, precise, and operationally honest.

The UI should communicate:

- pipeline progress,
- entity ownership,
- runtime health,
- research context,
- destructive risk.

It should not feel like a generic SaaS dashboard or a decorative crypto app.

## Canonical References

Use these as design source of truth, in this order:

1. [19_FRAME.md](19_FRAME.md)
2. [18_DESIGN_SYSTEM.md](18_DESIGN_SYSTEM.md)
3. [17_MENU_CONTROLS_BLUEPRINT.md](17_MENU_CONTROLS_BLUEPRINT.md)
4. `menu-sprint/codex-dark.html`

Important override:

- `19_FRAME.md` overrides `18_DESIGN_SYSTEM.md` where they conflict.
- Example: sidebar width is `380px`, not `320px`.

## Visual Direction

- Dark terminal-like workspace
- Monospace typography throughout
- Tight spacing, but not cramped
- Strong hierarchy through muted vs active surfaces
- Low ornament, high information density
- Color used semantically, not decoratively

## Screen Text Rule

- Do not place explanatory text, helper copy, commentary, or design rationale directly on product screens.
- On-screen text must be operational only: entity names, states, metrics, controls, empty/error states, and destructive warnings.
- If something needs explanation, put it in code comments or documentation, not in the UI.
- Short section labels are allowed. Explanatory sublabels under section headers are not.

## Border Rule

- Do not add borders, frames, or outlined containers unless they solve a real structural problem.
- A border must earn its place: separation of major surfaces, table structure, selected state, danger state, or input affordance.
- Do not wrap a small control in an extra framed capsule if the control itself is already clear.
- Prefer spacing, alignment, surface contrast, and typography before adding another line.

## Control Hierarchy Rule

- Buttons, badges, and chips must not collapse into one visual language.
- Buttons are actions and must look clickable.
- Chips are passive metadata and must look quieter than buttons.
- If chips and buttons appear in the same block, chips should not compete through matching borders, contrast, or hover affordance.

## Core Tokens

### Color Roles

- `--bg`: app background
- `--sidebar`: sidebar surface
- `--surface-hover`: row hover
- `--surface-active`: selected row
- `--border`, `--border-dim`: structural lines
- `--text`, `--text-muted`, `--text-dim`: text hierarchy
- `--green`: live / ok / nb✓
- `--amber`: idle / warn / nb⚠
- `--red`: danger / low sample / error
- `--blue`: neutral structural info
- `--purple`: Monte Carlo badge
- `--accent`: selected state and primary emphasis
- `--panel`, `--panel-alt`: content and utility surfaces

### Typography

- Font: `JetBrains Mono`, monospace
- Base size: `12px`
- `11px`: entity mono labels
- `10px`: meta text, buttons, group labels
- `9px`: badges and chips

Rules:

- use monospace everywhere,
- uppercase and letter-spacing only for labels, groups, and utility chrome,
- keep typography functional and compact.

## Layout Frame

```text
SIDEBAR 380px | CONTENT
              | context bar ~28px
              | sections
              | related entities
```

Rules:

- Sidebar always present.
- Sidebar scroll is independent from content scroll.
- Context bar sits at the top of content and is not sticky.
- Content does not need a big page hero or repeated page title block.
- Related entities section appears at the bottom of content on entity screens.
- Dashboard is the main exception: no related entities section there.

## Sidebar Model

Top-level zones:

- `Dashboard`
- `Collector`
- `Recordings`
- `Strategies`
- `Jupyter`

Do not make these top-level:

- `Quality`
- `Explorer`
- `Backtests (All)`
- `Monte Carlo (All)`
- `Paper (All)`
- `Trades`

Sidebar rows use:

- twisty for expandable nodes,
- dot for entity/status semantics,
- label and meta,
- at most one badge,
- one compact chip when useful.

Active node uses selected background plus accent border.

## Status Semantics

### Dots

- green: live / healthy / ready
- amber: idle / warning
- red: danger / low sample
- blue: neutral structural item

### Badges

Allowed short states:

- `LIVE`
- `running`
- `idle`
- `nb✓`
- `nb⚠`
- `low sample`
- `MC`

Badges communicate state only. They do not replace navigation or CTA.

## Navigation Model

Canonical URLs:

- `collector.html[?venue=X]`
- `recordings.html[?id=X]`
- `quality.html?id=X`
- `explorer.html?analysis=X`
- `strategy.html[?strategy=X]`
- `backtest.html?id=X`
- `montecarlo.html?bt_id=X`
- `paper.html?strategy=X`
- `trade.html?id=X&bt=Y`

Rules:

- label click navigates to canonical screen,
- expand/collapse must not break navigation,
- list view with no selected entity shows the full list,
- sidebar active state is derived from pathname plus URL params.

## Interaction Rules

### Allowed Menu Actions

Primary inline actions may include:

- `Analyze`
- `Run BT`
- `Run MC`
- `Start Paper`
- `Open Jupyter`
- `Refresh`

Context links may include:

- `Quality`
- `Explorer`
- `View`
- `Open Notebook`

### Constraints

- one primary action per row,
- delete only for selected row,
- max four compact buttons in action rail,
- overflow `...` avoided in first prototype,
- context links do not change ownership tree.

## Mutation Patterns

- No modal windows.
- No browser confirm dialogs.
- Inline forms expand beneath the relevant control or selected node.
- Delete uses inline confirmation strip with cascade consequences.
- Toasts appear in the context bar after mutation success.

## Progress and State Patterns

### Long Jobs

Show a thin progress bar under the active sidebar row for:

- analysis jobs,
- backtests,
- Monte Carlo runs,
- paper start,
- active recording.

The bar is visual only, no percentage text.

### Content States

Every major section should define:

- loading,
- empty,
- error,
- normal.

Empty states should point to the next pipeline step, not just say "no data".

## Absolute Bans

- no modal-first create/delete flows,
- no fake entities unsupported by the runtime,
- no overloaded rows with too many actions,
- no hidden power-user pattern as the primary path,
- no decorative dashboard cards that replace real entity navigation,
- no conflict with the Jupyter-first model.

## Practical Guidance

When in doubt:

1. preserve the real pipeline,
2. preserve real entity names and fields,
3. preserve the frame and sidebar model,
4. prefer detail pages over cramming actions into the menu,
5. keep the UI specific to LeadLag Lab, not generic.

## Source Documents

- [17_MENU_CONTROLS_BLUEPRINT.md](17_MENU_CONTROLS_BLUEPRINT.md)
- [18_DESIGN_SYSTEM.md](18_DESIGN_SYSTEM.md)
- [19_FRAME.md](19_FRAME.md)
- [20_WIREFRAMES.md](20_WIREFRAMES.md)
- `menu-sprint/codex-dark.html`
