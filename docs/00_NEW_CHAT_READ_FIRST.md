# DARMA GENERAL — NEW CHAT READ FIRST

**Authoritative continuation entrypoint**

Last synchronized with project conversation: **2026-08-29, V39 logo/typography code prepared on GitHub; latest confirmed production remains V38 until successful V39 server output**
Repository: `aliiitavazoeiii-afk/darma-general`
Production domain: `gozaresh.filmjadiid.ir`
Production server path: `/opt/darma-general`
Default branch: `main`

---

## STOP: read this before doing any work

This repository is a live business-management system replacing the user's Excel workflow. It contains real inventory, sales, receivables, cash/accounts, material stock, production and capital accounting. The application has been developed interactively over many revisions; some older files and older handoff documents remain for forensic/history purposes and are **not necessarily active**.

A new AI/chat must **not** infer current behavior from filenames like `v14`, `v19`, `v21`, etc. The only valid way to identify active source is:

1. Read this file completely.
2. Read every file in `docs/PROJECT_CONTEXT/` in numeric order, including V38 and V39 continuation files.
3. Read `UI_SAFETY_V37.md`, `UI_SAFETY_V38.md`, then `UI_SAFETY_V39.md` when working from/after the V39 Git state.
4. Read current `core/urls.py` and map each requested feature to its active view/module.
5. Read the exact active source files listed in `docs/PROJECT_CONTEXT/03_ACTIVE_CODE_MAP.md` before editing.
6. Read `AI_START_HERE.md` and `PROJECT_HANDOFF.md` **after** the new context pack for historical rationale only. Where they conflict with `docs/PROJECT_CONTEXT/*`, the new context pack wins.
7. Never assume code on `main` is already live. Use explicit user-posted server output to establish deployment status. At this synchronization point, V38 is explicitly confirmed live; V39 is prepared on GitHub but is not yet confirmed live. See `08_LIVE_STATE_AND_CHECKPOINTS.md`, `16_UI_MODERNIZATION_V38.md` and `17_LOGO_TYPOGRAPHY_V39.md`.
8. Before any data-affecting change, preserve rollback/backup/preflight discipline described in `06_DEPLOYMENT_SAFETY_AND_RECOVERY.md`.
9. After every important change and every confirmed successful deployment, update the relevant context-pack documents; after confirmed deployment also update `08_LIVE_STATE_AND_CHECKPOINTS.md` with the actual server snapshot rather than copying an older checkpoint.

---

## Non-negotiable project rule

**The accounting formulas and existing operational semantics are frozen unless the user explicitly asks to change the business rule.** UI cleanup must not silently alter accounting, stock, sales, Digikala fee, receivable, payment, raw-material, production, COGS, or SaleSnapshot behavior.

V38 remains the latest confirmed-live presentation baseline. V39 adds only the user's Darma logo and cleaner Persian typography. The V39 safety boundary is recorded in `UI_SAFETY_V39.md` and `docs/PROJECT_CONTEXT/17_LOGO_TYPOGRAPHY_V39.md`.

---

## Latest confirmed live checkpoint

The successful V38 UI deployment posted by the user ended with:

```text
SUCCESS: UI MODERNIZATION V38 DEPLOYED
```

Latest confirmed production snapshot:

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

The older V37 capital checkpoint was 5,441,972,371, while the V38 boundary is 5,430,972,371. The V38 deploy script proved its starting and final snapshots were identical, so the 11,000,000 difference occurred before the V38 deployment and must not be attributed to the UI change or force-reconciled without evidence.

Do **not** replace this confirmed-live checkpoint with V39 numbers until the user posts the actual successful V39 server output.

---

## What the new chat should know before changing code

Before editing, be able to answer all of the following from the repo/docs:

- What is the exact capital equation?
- How is finished inventory valued for Darma, Takvin, Novani and Anbaresh?
- Which brand/location does each sale or production flow affect?
- What is a SaleSnapshot and why must historical snapshots remain frozen?
- How does Digikala receivable move on sale, receipt and deletion?
- How do BusinessPayment V22 purchase/prepayment semantics work?
- What is the difference between Save / Apply Materials / Apply Output in material reports?
- What are the Darma HOME/KHORSHID rules and Novani single-bucket rule?
- What are the current Darma/Takvin/Novani size sets?
- What is the title-first Digikala resolver rule, including `D-220` vs `rah-220`, Takvin `1-654`, and brandless model 400?
- What does code `06` contain now?
- Which model is authoritative for actual sold colors (`SaleAllocation`) versus current pack definition (`ProductComposition`)?
- Which model is authoritative for cumulative material output (`MaterialReportOutputApplied`) versus saved form JSON?
- What does standalone return V37 do, and what must it never do?
- How does the V37 target-price calculator preserve current realized margin while using the existing Digikala fee engine?
- What changed in V38 and why is it presentation-only?
- What changed in V39, including the Darma logo asset and cleaner Persian typography, and why is it still presentation-only?
- Which deployment scripts are historical/destructive and must never be casually rerun?
- What is the most recent confirmed live state?

If any of these are unclear, stop and read the context/code before modifying anything.

---

## Required reading order

Read exactly in this order:

1. `docs/PROJECT_CONTEXT/01_BUSINESS_RULES_AND_INVARIANTS.md`
2. `docs/PROJECT_CONTEXT/02_ACCOUNTING_FORMULAS_AND_LEDGER_SEMANTICS.md`
3. `docs/PROJECT_CONTEXT/03_ACTIVE_CODE_MAP.md`
4. `docs/PROJECT_CONTEXT/04_SALES_DIGIKALA_AND_RETURNS.md`
5. `docs/PROJECT_CONTEXT/05_INVENTORY_MATERIALS_PRODUCTION_PAYMENTS.md`
6. `docs/PROJECT_CONTEXT/06_DEPLOYMENT_SAFETY_AND_RECOVERY.md`
7. `docs/PROJECT_CONTEXT/07_BUG_HISTORY_AND_DO_NOT_REPEAT.md`
8. `docs/PROJECT_CONTEXT/08_LIVE_STATE_AND_CHECKPOINTS.md`
9. `docs/PROJECT_CONTEXT/09_UI_AND_USER_WORKFLOW_CONTRACT.md`
10. `docs/PROJECT_CONTEXT/10_EXACT_BASELINES_CATALOG_AND_SPECIAL_CASES.md`
11. `docs/PROJECT_CONTEXT/11_DATA_MODEL_AND_LEDGER_RELATIONSHIPS.md`
12. `docs/PROJECT_CONTEXT/12_VERSION_TIMELINE_V18_TO_V37.md`
13. `docs/PROJECT_CONTEXT/13_NEW_CHAT_OPERATING_PROTOCOL.md`
14. `docs/PROJECT_CONTEXT/14_HANDOFF_SCOPE_AND_COMPLETENESS.md`
15. `docs/PROJECT_CONTEXT/15_CODE_FINGERPRINT_AT_HANDOFF.md`
16. `docs/PROJECT_CONTEXT/16_UI_MODERNIZATION_V38.md`
17. `docs/PROJECT_CONTEXT/17_LOGO_TYPOGRAPHY_V39.md`
18. `UI_SAFETY_V37.md`
19. `UI_SAFETY_V38.md`
20. `UI_SAFETY_V39.md`
21. current `core/urls.py`
22. relevant active implementation files from `03_ACTIVE_CODE_MAP.md`
23. `AI_START_HERE.md` and `PROJECT_HANDOFF.md` for older history only

`docs/PROJECT_CONTEXT/README.md` is the manifest for the pack.

---

## One-line prompt for a new ChatGPT conversation

The user can paste only this:

> Open my GitHub repo `aliiitavazoeiii-afk/darma-general`. Read `docs/00_NEW_CHAT_READ_FIRST.md` completely, then read every file it requires in order, then inspect the current active source files/routes before answering. Treat the context pack as authoritative over older handoff docs. Do not change anything until you understand all accounting/inventory/sales/material/payment invariants, model/ledger sources of truth, historical pitfalls, the confirmed-live V38 UI baseline, the V39 logo/typography delta, and the latest confirmed live state. Continue the project as if you were continuing the original development chat.

That prompt is intentionally enough; the new chat should retrieve the rest from GitHub.
