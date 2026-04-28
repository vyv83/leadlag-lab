# 16 Implementation Plan

## Legend

- `[1]` = single entity
- `[*]` = array of entities
- `group` = visual menu grouping, not a domain entity
- `-> ref` = cross-link, not tree ownership

---

## Entity Rule

Entity in `leadlag-lab`:

1. Can be created by user action or by a pipeline started from user action.
2. Exists as a standalone operational object.
3. Must be visible and navigable in the menu tree.

Not an entity:

1. Buttons and actions.
2. Pages and views.
3. Params and metrics.
4. `json` files that only store properties.
5. Project source files and docs.

---

## Domain Entities

1. `Collector Run`
2. `Venue`
3. `Recording`
4. `Ticks`
5. `BBO`
6. `Analysis`
7. `Bins`
8. `Strategy`
9. `Notebook`
10. `Backtest`
11. `Monte Carlo`
12. `Paper Run`
13. `Trade`

---

## Ownership Rules

1. `Collector Run` owns `Venue[*]`
2. `Collector Run` produces `Recording[*]`
3. `Recording` owns `Ticks`
4. `Recording` owns `BBO`
5. `Recording` owns `Analysis[*]`
6. `Analysis` owns `Bins`
7. `Strategy` owns `Notebook[1]`
8. `Strategy` owns `Backtest[*]`
9. `Backtest` owns `Trade[*]`
10. `Backtest` owns `Monte Carlo[*]`
11. `Strategy` owns `Paper Run[*]`
12. `Paper Run` owns `Trade[*]`

Cross-link:

1. `Backtest -> ref Analysis[1]`
2. `Analysis -> related Backtest[*]`

---

## Canonical Menu Shape

```text
LeadLag Lab [1]
├── Dashboard [1]
├── Collector [1]
│   └── Collector Run [1]
│       └── Venues [group]
│           └── Venue [*]
├── Recordings [group]
│   └── Recording [*]
│       ├── Market Data [group]
│       │   ├── Ticks [1]
│       │   └── BBO [1]
│       └── Analyses [group]
│           └── Analysis [*]
│               └── Bins [1]
├── Strategies [group]
│   └── Strategy [*]
│       ├── Notebook [1]
│       ├── Backtests [group]
│       │   └── Backtest [*]
│       │       ├── Trades [group]
│       │       │   └── Trade [*]
│       │       └── Monte Carlo Runs [group]
│       │           └── Monte Carlo [*]
│       └── Paper Runs [group]
│           └── Paper Run [*]
│               └── Trades [group]
│                   └── Trade [*]
└── Jupyter [1]
```

---

## Full Expanded Menu

```text
LeadLag Lab [1]

Dashboard [1]

Collector [1]
  Collector Run [1]
    Venues [group]
      Venue [*]

Recordings [group]
  Recording [*]
    Market Data [group]
      Ticks [1]
      BBO [1]
    Analyses [group]
      Analysis [*]
        Bins [1]

Strategies [group]
  Strategy [*]
    Notebook [1]
    Backtests [group]
      Backtest [*]
        Trades [group]
          Trade [*]
        Monte Carlo Runs [group]
          Monte Carlo [*]
    Paper Runs [group]
      Paper Run [*]
        Trades [group]
          Trade [*]

Jupyter [1]
```

---

## Cross-Hierarchy Relation

```text
Backtest [*] = Strategy [1] × Analysis [1]
```

Meaning:

1. `Backtest` is owned by `Strategy` in the menu tree.
2. Each `Backtest` references one `Analysis`.
3. One `Analysis` can be used by many `Backtest[*]`.
4. Related backtests should be visible on the `Analysis` page, but not as second ownership in the tree.

---

## What Must Stay On Pages

1. `Quality`
2. `Explorer`
3. Analysis params
4. Strategy params
5. Backtest stats
6. Backtest equity
7. Venue metrics
8. Any `json` payloads
9. Any run, delete, compare, optimize, or re-analyze controls

