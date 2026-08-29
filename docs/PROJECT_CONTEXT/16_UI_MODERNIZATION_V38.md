# 16 — UI MODERNIZATION V38

This file records the first meaningful project change after the exhaustive V37 handoff pack.

Status at creation: **committed to GitHub, NOT YET CONFIRMED LIVE**.

The latest confirmed production version remains V37 until the user posts successful VPS deployment output.

---

## 1. User requirement

The user requested a site-wide visual cleanup and modernization with an absolute constraint:

> improve visual defects and make the site more attractive/current without making the slightest change to formulas or calculations.

Therefore V38 is classified as **UI-only / presentation-only**.

No business-rule change is authorized.

---

## 2. Pre-change safety state

Pre-V38 `main` commit:

```text
b488fee9701e1a4b4c266dd92aa371db5d159e99
```

A rollback branch was created before the UI modification:

```text
before-ui-modernization-v38-20260829
```

This branch points to the pre-V38 Git state only. It is not a database rollback.

---

## 3. V38 application-code scope

The only application presentation file intentionally modified in the initial V38 implementation is:

```text
static/core/ui-polish.css
```

First V38 UI commit:

```text
ead072e8c994f449674f339bc6cb47c634d3cf89
```

No V38 business implementation change was made to:

- `core/*.py`;
- `core/urls.py`;
- models;
- migrations;
- templates;
- workflow JavaScript;
- database data;
- accounting settings.

This is intentional. Existing routes, forms, POST targets, view contexts and calculations remain the same.

---

## 4. Visual changes

The appended V38 global UI layer modernizes the existing DOM rather than rebuilding workflows.

It includes:

- a darker, cleaner navy background with more restrained ambient gradients;
- refined true-glass cards and panel hierarchy;
- improved sidebar spacing, active states and visual hierarchy;
- refined sticky top bar;
- stronger page-title/KPI typography;
- cleaner buttons and focus states;
- modern form controls;
- cleaner tables, scroll containers and hover states;
- updated badges, alerts and status treatments;
- improved comprehensive-report/capital visual surfaces;
- improved material-report surfaces without changing material semantics;
- tablet/mobile spacing refinements;
- reduced-motion accessibility support.

The existing Vazirmatn + orange-accent + dark-navy design contract remains in force.

---

## 5. Business invariants explicitly frozen in V38

V38 must not change any behavior in:

- capital equation;
- finished inventory valuation;
- raw-material valuation;
- Digikala canonical fee;
- Digikala receivable;
- SaleSnapshot;
- SaleAllocation;
- normal/manual/Digikala sale inventory flow;
- daily XLSX replacement/idempotency;
- title resolver;
- material Save / Apply Materials / Apply Output separation;
- Darma/Novani output destinations;
- sewing wage;
- payments/material purchase/prepayment reversal;
- Digikala receipts;
- inventory adjustments/transfers;
- standalone returns V37;
- calculator V37;
- dashboard alert query semantics.

A cosmetic change that changes any economic value is a bug.

---

## 6. V38 deployment guard

Purpose-specific deploy script:

```text
server_ui_modernization_v38.sh
```

The script is intentionally stricter than an ordinary CSS deployment. It:

1. starts/checks PostgreSQL;
2. takes a full `pg_dump` backup;
3. captures the current live economic snapshot;
4. checks Git diff scope against the exact pre-V38 main commit;
5. rejects changes to Python, routes, templates, migrations or workflow JavaScript;
6. builds the latest web image;
7. runs `makemigrations --check --dry-run`;
8. runs Django `check`;
9. runs the current V37 returns/calculator regression check;
10. verifies the V38 CSS marker/basic source safety;
11. compares new-image economic values with live values before recreating web;
12. recreates web and restarts Caddy only after preflight succeeds;
13. reruns live checks;
14. compares final economic values byte-for-byte with the starting snapshot.

Protected snapshot fields:

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

Any difference fails deployment.

Explicit success marker:

```text
SUCCESS: UI MODERNIZATION V38 DEPLOYED
```

Do not call V38 live until this marker and final snapshot are provided by the user.

---

## 7. Live-state rule

At the time this file is written:

- GitHub contains the V38 UI implementation;
- production has **not** been confirmed on V38;
- `08_LIVE_STATE_AND_CHECKPOINTS.md` must therefore remain on the last confirmed V37 production state.

After successful V38 server output is posted, update `08_LIVE_STATE_AND_CHECKPOINTS.md` with:

- confirmed V38 success marker;
- deployment date;
- deployed commit if shown/verified;
- final CAPITAL/FINISHED/RAW/DIGI/DARMA/TAKVIN/NOVANI/SALES/ACCOUNT_ENTRIES values.

Do not copy the old V37 checkpoint forward as though it were the current DB state; use the actual V38 server output.

---

## 8. Continuation rule

For any follow-up visual refinement after V38:

- keep the change in presentation layers where possible;
- inspect the exact active page/template before changing page-specific layout;
- do not modify Python merely to make a visual number look different unless the user explicitly requests a semantic change;
- preserve forms, field names, URL names, HTMX targets and POST behavior;
- run the same economic invariant comparison on deployment.
