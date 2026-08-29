# UI SAFETY V38

V38 is a presentation-only modernization pass.

## User requirement

The site may become cleaner, more modern, more attractive and more responsive, but **no accounting, inventory, sales, Digikala, COGS, material, production, payment, receivable, return, snapshot or ledger formula/behavior may change**.

## V38 operational scope

The only application presentation asset intentionally changed in V38 is:

```text
static/core/ui-polish.css
```

No V38 change is required in:

- `core/*.py`
- models or migrations
- `core/urls.py`
- active templates
- JavaScript business/workflow code
- database rows
- accounting settings

The existing DOM, forms, URLs, POST targets, context values and calculations are retained.

## Visual changes

V38 adds a global visual layer for:

- darker and more restrained navy background;
- clearer true-glass cards;
- improved sidebar and active navigation states;
- refined sticky top bar;
- stronger typography hierarchy;
- cleaner KPI cards;
- modern inputs, buttons, badges and alerts;
- cleaner table headers/rows and scroll containers;
- improved report/capital/material visual surfaces;
- improved responsive/mobile spacing;
- reduced-motion support.

## Protected business boundary

The V38 deploy must verify that the following source families are unchanged from the pre-V38 main baseline:

- sales/import/allocation/snapshot code;
- finance and Digikala fee code;
- capital/report calculation code;
- finished/raw inventory code;
- material consumption/output/wage code;
- payments/purchases/prepayments code;
- Digikala receipts code;
- returns V37 code;
- calculator V37 code;
- routes and active templates.

## Economic invariant check

The deploy must capture and compare before/preflight/after values for:

```text
CAPITAL
FINISHED
RAW
DIGI
DARMA
TAKVIN
NOVANI
SALES
ACCOUNT_ENTRIES
```

Every value must be byte-for-byte identical across a V38 cosmetic deploy. Any difference is a deployment failure and must not be normalized or manually balanced.

## Git safety

Pre-V38 rollback branch:

```text
before-ui-modernization-v38-20260829
```

Pre-V38 main commit:

```text
b488fee9701e1a4b4c266dd92aa371db5d159e99
```

First V38 UI commit:

```text
ead072e8c994f449674f339bc6cb47c634d3cf89
```

The rollback branch is a Git/code anchor only. It is not a database rollback.

## Live-state rule

V38 must **not** be recorded as production-live until the VPS prints the explicit successful deployment marker from `server_ui_modernization_v38.sh` and its final invariant snapshot is available.

Until then, the latest confirmed production version remains V37.
