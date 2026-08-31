# DARMA GENERAL — NEW CHAT READ FIRST

**Authoritative continuation entrypoint**

Last synchronized with project conversation: **2026-08-31, V45 Dia Gallery daily-sales channel prepared on GitHub; V44/V45 are not production-confirmed without successful server output**
Repository: `aliiitavazoeiii-afk/darma-general`
Production domain: `gozaresh.filmjadiid.ir`
Production server path: `/opt/darma-general`
Default branch: `main`

---

## STOP: read this before doing any work

This repository is a live business-management system replacing the user's Excel workflow. It contains real inventory, sales, receivables, cash/accounts, material stock, production and capital accounting. Older versioned files remain for history and are not necessarily active.

A new AI/chat must:

1. Read this file completely.
2. Read every file in `docs/PROJECT_CONTEXT/` in numeric order, now through `23_DIA_GALLERY_V45.md`.
3. Read `UI_SAFETY_V37.md` through `UI_SAFETY_V45.md`.
4. Read current `core/urls.py` before deciding which source is active.
5. Read exact active source files for the requested subsystem.
6. Read `AI_START_HERE.md` and `PROJECT_HANDOFF.md` last for historical rationale only.
7. Never equate GitHub `main` with production. Require user-posted successful server output before calling a revision live.
8. Preserve backup/preflight/invariant discipline from `06_DEPLOYMENT_SAFETY_AND_RECOVERY.md`.
9. After every important change update context docs; after every confirmed deployment update `08_LIVE_STATE_AND_CHECKPOINTS.md` using the actual final server snapshot.

---

## Non-negotiable project rule

**Accounting formulas and existing operational semantics are frozen unless the user explicitly changes a business rule.** External Digikala visibility must not silently alter internal stock, sales, fees, receivable, payments, materials, production, COGS, SaleSnapshots or capital.

V40 introduced read-only Digikala API access. V41 corrected the operational commitment number. V42 derived free/sellable Digikala warehouse stock. V43 reorganized Digikala into a separate mini-app. V44 corrects real V43 observations while keeping the same read-only boundary. V45 is a separate explicitly requested business feature: a Dia Gallery daily-sales channel that consumes Darma stock, sells each short at a fixed 71,000 toman, creates its own receivable, and contributes sale profit to capital.

---

## Latest confirmed numeric live checkpoint

The last numerically confirmed production deployment remains V38:

```text
CAPITAL=5430972371
FINISHED=1115731500
RAW=1994448050
DIGI=812517154
DARMA=12072
TAKVIN=1195
NOVANI=3630
SALES=202
ACCOUNT_ENTRIES=206
```

Backup:

```text
backups/before-ui-modernization-v38-20260829-223111.sql
```

Do not invent or copy forward a newer numeric checkpoint without actual server invariant output. The user has interacted with later Digikala pages, but no newer final invariant block has been posted in chat.

---

## Digikala Open API status and evolution

Authentication is complete. Runtime access/refresh tokens live under `/opt/darma-secrets/digikala/runtime` and are mounted at `/run/secrets/digikala`; the RSA private key remains outside the web container. Refresh rotates both access and refresh tokens atomically.

Initial read-only probes confirmed HTTP 200 for orders, order statistics, inventory, profile, commitments, commitment metadata and invoices. Insight endpoints remain excluded because they returned server/validation errors.

V41 reconciliation established the seller-panel commitment semantics:

```text
total commitments=202
effective commitments=201
commitments list: 69 variants, nextDays=201, today=0, delayed=1, all=202
```

V42 established the read-only free warehouse formula from live inventory/reservation evidence. Those observed counts are not constants.

V43 created the isolated `/digikala/` mini-app with daily orders, packages, sales, warehouse and returns.

### V44 corrections — current Digikala Git source of truth

The user opened the V43 pages and reported:

- tomorrow/day-after were empty while all future quantity stayed in later;
- old/current products were not visible through the attempted product path;
- sales report request failed;
- opening Digikala sections was slow;
- the returns page showed sellable items, while actual returns physically live in a warehouse titled `انبار مرجوعی` / `انبار مرجوعی مرکزی`.

V44 therefore:

- removes `search[is_effective]=true` from future cumulative commitment cutoffs;
- derives tomorrow/day-after using cumulative `search[to_commitment_date]` and preserves the future-quantity identity;
- adds `/digikala/products/` from Inventory API rows grouped by DKP;
- tries order history first for sales and removes speculative sort parameters;
- defines returns by nested warehouse entries whose title contains `مرجوعی` rather than top-level `return_stock`;
- shares API caches between Gunicorn workers and uses bounded concurrent pagination;
- makes Digikala home API-light.

See `22_DIGIKALA_CENTER_V44.md` and `UI_SAFETY_V44.md`.

---

## Dia Gallery V45 — new explicit business rule

V45 adds a separate box under the existing daily-sales date screen:

```text
Dia Gallery
```

It is not a new inventory brand. It is a sales channel for physical Darma goods.

Rules:

- enter direct Darma color × Darma size quantities;
- one entered unit = one short;
- fixed price = **71,000 toman per short**;
- no Digikala fee;
- physical stock is deducted from Darma using existing HOME/KHORSHID primitives;
- dedicated receivable account title = `فروش Dia Gallery`;
- receivable delta = `quantity × 71,000`;
- Dia receivable is included in the accounts component of capital;
- historical Dia row freezes its Darma inventory unit cost for COGS/profit;
- Dia sales are separate from `SaleLine`, so Digikala XLSX replacement must never erase or replace them;
- dashboard, daily report and comprehensive report include Dia sales;
- the accounts / ریز حساب‌ها UI shows the Dia receivable as an automatic row.

Capital logic is not replaced. Dia enters the existing equation through the accounts asset side while Darma stock value decreases, so a sale changes capital by `gross - COGS`.

See `23_DIA_GALLERY_V45.md` and `UI_SAFETY_V45.md`.

---

## Core business facts that must remain understood before editing

A new chat must know from the context pack:

- the exact capital equation and valuation sources;
- SaleSnapshot freeze semantics;
- SaleAllocation as historical physical color source;
- title-first Digikala XLSX resolution and seller-code discard;
- Darma/Takvin/Novani size/location rules;
- V22 payment and material-report semantics;
- standalone return V37 HOME-only behavior;
- the exact Digikala fee engine;
- V40 token/security boundary;
- V41 commitment semantics;
- V42 free warehouse derivation;
- V43 isolated Digikala-center architecture;
- V44 future-date split, inventory-backed products, physical return-warehouse rule and shared-cache performance changes;
- V45 Dia Gallery fixed-price sale, Darma-stock, dedicated-receivable and capital semantics;
- which historical deploy/reset scripts are unsafe to rerun;
- that the latest numerically confirmed checkpoint is still V38 until a newer actual server block is posted.

If any are unclear, stop and read the numbered context files and active code before changing anything.

---

## Required reading order

Read exactly:

1. `docs/PROJECT_CONTEXT/01_BUSINESS_RULES_AND_INVARIANTS.md`
2. `02_ACCOUNTING_FORMULAS_AND_LEDGER_SEMANTICS.md`
3. `03_ACTIVE_CODE_MAP.md`
4. `04_SALES_DIGIKALA_AND_RETURNS.md`
5. `05_INVENTORY_MATERIALS_PRODUCTION_PAYMENTS.md`
6. `06_DEPLOYMENT_SAFETY_AND_RECOVERY.md`
7. `07_BUG_HISTORY_AND_DO_NOT_REPEAT.md`
8. `08_LIVE_STATE_AND_CHECKPOINTS.md`
9. `09_UI_AND_USER_WORKFLOW_CONTRACT.md`
10. `10_EXACT_BASELINES_CATALOG_AND_SPECIAL_CASES.md`
11. `11_DATA_MODEL_AND_LEDGER_RELATIONSHIPS.md`
12. `12_VERSION_TIMELINE_V18_TO_V37.md`
13. `13_NEW_CHAT_OPERATING_PROTOCOL.md`
14. `14_HANDOFF_SCOPE_AND_COMPLETENESS.md`
15. `15_CODE_FINGERPRINT_AT_HANDOFF.md`
16. `16_UI_MODERNIZATION_V38.md`
17. `17_LOGO_TYPOGRAPHY_V39.md`
18. `18_DIGIKALA_API_V40.md`
19. `19_DIGIKALA_DELIVERIES_V41.md`
20. `20_DIGIKALA_FREE_WAREHOUSE_V42.md`
21. `21_DIGIKALA_CENTER_V43.md`
22. `22_DIGIKALA_CENTER_V44.md`
23. `23_DIA_GALLERY_V45.md`
24. `UI_SAFETY_V37.md`
25. `UI_SAFETY_V38.md`
26. `UI_SAFETY_V39.md`
27. `UI_SAFETY_V40.md`
28. `UI_SAFETY_V41.md`
29. `UI_SAFETY_V42.md`
30. `UI_SAFETY_V43.md`
31. `UI_SAFETY_V44.md`
32. `UI_SAFETY_V45.md`
33. current `core/urls.py`
34. relevant active implementation files
35. `AI_START_HERE.md` and `PROJECT_HANDOFF.md` last

`docs/PROJECT_CONTEXT/README.md` is the manifest.

---

## One-line continuation prompt

> Open my GitHub repo `aliiitavazoeiii-afk/darma-general`. Read `docs/00_NEW_CHAT_READ_FIRST.md`, then every required context file in order through V45, then current routes and exact active source. Treat the context pack as authoritative. Preserve all frozen accounting/inventory/sales/material/payment invariants and the Digikala read-only boundary. Understand Dia Gallery V45 as its own direct Darma-stock sales channel. Never assume GitHub code is live without user-posted deploy output.
