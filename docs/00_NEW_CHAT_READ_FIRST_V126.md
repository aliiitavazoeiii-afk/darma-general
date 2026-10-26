# DARMA GENERAL — READ FIRST FOR ALL NEW AI/CHAT SESSIONS
**Prepared:** 2026-10-26 (1405/08/04) — documentation-only handoff, not a production release.
**Functional source:** `v126-payment-history-filters` @ `90a79e993adced1689c70d5b0777ce2ea7f2789f`.
**Docs branch:** `docs-v126-complete-handoff-1405-08`.
**Production:** `https://gozaresh.filmjadiid.ir`, checkout `/opt/darma-general`.
**Owner:** explicitly confirmed V126 payment-date filter "اوکی شد" in conversation after installation; this is NOT verified live server Git SHA/DB totals.

## IMPORTANT — old "CURRENT" docs are out of date
`docs/00_NEW_CHAT_READ_FIRST.md` was last synchronized through V108 and `AI_START_HERE.md` originally through V37. Those have extensive valuable forensic background, but **their last-current-branch claim is obsolete**.
Start with this file and new authoritative documents 75–77. The old chronological docs remain intentionally unmodified historical records; do not interpret V122 previous-month carryover, V119 Pedram sign rule, or V52/53 inventory thresholds as today's rules. See explicit supersession list in the master.

## Mandatory reading order
1. `DARMA_NEW_CHAT_PROMPT_V126.md` — owner's ready-to-paste new chat instruction.
2. `docs/PROJECT_CONTEXT/75_MASTER_HISTORY_AND_FINAL_DECISIONS_V126.md` — full historical versions + final decisions, particularly V46, V108, V119–V126.
3. `docs/PROJECT_CONTEXT/76_ACTIVE_MODULE_AND_LEDGER_MAP_V126.md` — active route-to-Django code map, StockBalance/RawMaterialStock/BusinessPayment, signed tailor ledger, canonical cash/cut calculation.
4. `docs/PROJECT_CONTEXT/77_DEPLOYMENT_AND_CHANGE_PROTOCOL_V126.md` — tests, safe changes, branch discipline, one-time repairs, PostgreSQL backup, immutable business snapshots.
5. `PROJECT_HANDOFF_CURRENT.md` + `docs/PROJECT_CONTEXT/README.md` — progressively appended detailed feature handoffs and numbered links.
6. Historical forensic detail: `docs/00_NEW_CHAT_READ_FIRST.md`, `docs/PROJECT_CONTEXT/01_...` through `74_...`, including specific feature notes; latest documents override obsolete earlier rules.
7. Actual functional `core/urls.py`, active views/templates/services/models/migrations and GitHub CI runs on `v126-payment-history-filters`. If debugging runtime, require read-only VPS confirmation of current branch/container DB.

## Most important final owner contracts
- Darma sales debit HOME only; KHORSHID warehouse changes by explicit manual transfer (V46).
- A current-month materials KPI only counts current-month colors with **unapplied raw fabric**, no carryover. Old months collapsed by default (V123).
- Clicking archived month selects and opens that month's report, with a separate per-color ALL finished-delivery debt panel including already-applied raw material (V125).
- Same-color roll deficits/surpluses net before clamping; registered delivery versus applied stock different (V122/V125).
- Apply raw materials per ONE selected color, with accurate shared elastic allocation and idempotence (V123, migration 0021).
- Stock transfers bidirectional HOME<->KHORSHID with default warehouse->home restored on real refresh (V123); zero strong red/1..9 light/10+ normal (V123).
- Darma panel live colors offered in new/edit fabric payment; old nine keys preserved (V124).
- Payments date-filtered actual cash sum and full all-time total across every `BusinessPayment`, not only 100 visible rows, while receipts V91 filters remain (V126).
- Novani wholesale is separate; V121 Pedram shared tailor signed account must ADD invoice gross, wages subtract. Historical repair is never repeated without dry-run/owner approval.
- Native Finance sidebar and exactly three Finance-root cards; do not change accounting/fee/cost snapshots for cosmetic requests.
- Strict no unintended migrations, cash/stock ledger writes, Caddyfile edits, resets, automatic stock moves or cross-repo changes.

## Where to find the historic versions
`docs/PROJECT_CONTEXT/README.md` is the manifest of 01–74. Their v18–v37 detailed history is in `12_VERSION_TIMELINE_V18_TO_V37.md`; older module invariants in 01–15; dated stage docs 16–74. New 75–77 are an **index/continuation** rather than deleting any history. The presence of an old safe-deploy script is not a signal to execute it.

## Exact links in GitHub
- [Paste-ready new chat prompt](https://github.com/aliiitavazoeiii-afk/darma-general/blob/docs-v126-complete-handoff-1405-08/DARMA_NEW_CHAT_PROMPT_V126.md)
- [Complete historical decisions](https://github.com/aliiitavazoeiii-afk/darma-general/blob/docs-v126-complete-handoff-1405-08/docs/PROJECT_CONTEXT/75_MASTER_HISTORY_AND_FINAL_DECISIONS_V126.md)
- [Module and ledger map](https://github.com/aliiitavazoeiii-afk/darma-general/blob/docs-v126-complete-handoff-1405-08/docs/PROJECT_CONTEXT/76_ACTIVE_MODULE_AND_LEDGER_MAP_V126.md)
- [Safety and deployment](https://github.com/aliiitavazoeiii-afk/darma-general/blob/docs-v126-complete-handoff-1405-08/docs/PROJECT_CONTEXT/77_DEPLOYMENT_AND_CHANGE_PROTOCOL_V126.md)
- [Functional code base V126](https://github.com/aliiitavazoeiii-afk/darma-general/tree/v126-payment-history-filters)

## Last instruction
Do not change production, issue repairs or run a deploy simply because this handoff was written. First read, check active code and summarize current understanding; wait for the owner's next real feature request.
