# PROJECT_CONTEXT MANIFEST

This directory is the authoritative, detailed continuation pack for a new AI/chat.

Read `../00_NEW_CHAT_READ_FIRST.md` first. As of 2026-09-03 that entrypoint contains the complete current-chat handoff through V50, including canonical formulas/rules, the daily-report V48 incident, V49/V50 inventory-operation semantics, deployment-status uncertainty, the UI rollback history, exact do-not-repeat rules, and the one-shot next-chat prompt. Then continue through the numbered context files below; V51 through V60 are newer follow-ups after that handoff.

Then read all numbered files in order:

1. `01_BUSINESS_RULES_AND_INVARIANTS.md`
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
22. `22_DIGIKALA_CENTER_V44.md` — fixes future-date commitment split, inventory-backed old/current products, sales endpoint fallback, physical return-warehouse detection, and multi-worker/shared API caching.
23. `23_DIA_GALLERY_V45.md` — separate daily sales channel consuming Darma color/size stock at fixed 71,000 toman per short, with its own receivable included in accounts/capital.
24. `24_NO_AUTO_TRANSFER_V46.md` — explicit new rule: every Darma-backed sale deducts HOME only and may make HOME negative; KHORSHID changes only through explicit manual transfer; post-day-3 phantom auto-transfers are reversed without changing combined stock/capital.
25. `25_BLACK_RED_UI_V47.md` — reversible presentation-only black/charcoal/red runtime theme, dark Darma logo plaque, aligned comprehensive-report KPI grid, DB/UI backup, and one-command rollback.
26. `26_DAILY_REPORT_STABILITY_V48.md` — fixes the active saved-day daily-report HTTP 500 caused by a missing child-template tag-library load and adds a read-only runtime render smoke test for every historical sales day.
27. `27_INVENTORY_OPERATIONS_V49.md` — changes manual stock correction input from delta to absolute counted stock while preserving delta audit records, and replaces one-color-at-a-time Darma transfer entry with one size + all colors in a single atomic fixed KHORSHID -> HOME batch.
28. `28_INVENTORY_OPERATIONS_V50.md` — makes both inventory-operation cards compact and changes absolute stock correction to one date/brand/size/location selection plus all colors for that brand in one atomic physical-count submit; blank means unchanged and explicit zero means final stock zero.
29. `29_INVENTORY_ADJUSTMENT_DELETE_V51.md` — adds a guarded delete/reversal action only for manual V50 `InventoryAdjustment` rows in the recent movement table; exact delta is reversed to restore the pre-correction quantity, while deletion is blocked if any newer movement exists on that same stock cell. Standalone-return V37 adjustments are explicitly excluded from this delete surface.
30. `30_INVENTORY_THRESHOLD_HIGHLIGHTS_V52.md` — presentation-only low-stock highlighting on active inventory tables: HOME below 30 red; TOTAL below 50 red and 50–99 orange; requested yellow/red/bear/black-ribbed/navy-stripe/leopard models are exempt; KHORSHID and all quantities/formulas remain unchanged.
31. `31_INVENTORY_TOTAL_RED_STRENGTH_V53.md` — presentation-only refinement of V52: in the TOTAL table, the former 50–99 orange band now uses the previous red visual, while the below-50 critical band uses a much brighter red; thresholds, exemptions, HOME and KHORSHID behavior remain unchanged.
32. `32_DAILY_SALE_DAY_DELETE_V54.md` — adds a guarded POST-only **حذف صورت روز** action beside the sales calendar on the active daily report; it atomically reverses SaleLine/Digikala, Anbaresh-backed Darma stock, variable `s3`, and Dia Gallery stock/receivable effects before deleting the SaleDay, while preserving unrelated same-date business activity and blocking unsafe historical rows without authoritative allocations.
33. `33_DARMA_COST_RULE_V55.md` — replaces Darma color/size accounting-cost drift with one date-effective per-short Darma cost source used by new Darma/Anbaresh/s3 snapshots, Dia, missing-snapshot COGS fallback, current Darma inventory valuation, returns and physical adjustments; seeds the confirmed 61,000 baseline and repairs only 12 + 14 Shahrivar 1405 cost snapshots.
34. `34_DARMA_INVENTORY_PAGE_COST_V56.md` — fixes the active inventory page that still valued Darma from legacy color×size `InventoryModelCost`; Darma cell/size/grand inventory values now use only the current V55 central rate and the add-color UI no longer exposes a separate Darma cost input.
35. `35_RETURNS_REPORT_EDIT_DELETE_V57.md` — exposes existing standalone-return V37 groups as visible return forms under `/returns/`, with grouped view, date/quantity edit, and guarded exact deletion that reverses only the return's own HOME adjustments/movements while preserving later unrelated stock movements and all sales/Digikala/accounting ledgers.
36. `36_RETURNS_MULTI_SIZE_V58.md` — removes the one-size-at-a-time entry workflow for new returns: all allowed sizes render under one shared date/form and one atomic submit, while each populated size remains a separate V57 report for exact view/edit/delete compatibility.
37. `37_COST_RULES_TAKVIN_PURCHASE_V59.md` — adds a single date-effective Novani per-short accounting cost parallel to Darma and fixes the active Takvin purchase page so purchases add exact HOME inventory alongside debt; includes an idempotent repair for today's legacy purchase rows that increased debt without adding stock.
38. `38_SALE_PRICE_ELASTIC_MULTI_V60.md` — makes Darma and Takvin selling prices date-effective by SaleDay while freezing every saved SaleLine price, routes manual/XLSX sales through the dated default, adds a Jalali start date to per-product and bulk Darma pricing, and allows one elastic payment to contain all purchased colors with independent 16/25 quantities and prices.
39. `39_DIGIKALA_ZERO_GUARD_V65.md` — SAFE MODE Telegram guard for Darma combined-stock zero transitions: sends a private alert, GETs current Digikala variants only on preview, maps title/size through existing resolvers, and shows affected DKPCs while real activation/seller-stock writes remain completely absent and locked.

Important supersession rule for V46: older statements in `01`/`05` that sale logic may auto-transfer KHORSHID -> HOME are obsolete. `24_NO_AUTO_TRANSFER_V46.md` and the explicit V46 section in `00_NEW_CHAT_READ_FIRST.md` are authoritative for sale location behavior.

Important supersession rule for V55/V56/V59: Darma and Novani accounting costs are single date-effective per-short sources. Darma uses `darma_cost_for(date)` and Novani uses `novani_cost_for(date)`. Legacy per-color/per-size `InventoryModelCost` and ProductSize unit-cost fields must not drive Darma/Novani current capital valuation or sale COGS. Takvin remains size-specific and date-effective through its own rule set.

Important V57/V58 return rule: standalone V37 returns are grouped from their existing `[standalone-return-v37] group=...` `InventoryAdjustment` audit rows. Editing/deleting a return may change only that return's HOME stock contribution and its exact adjustment/movement records. V58 new-entry submits may contain multiple sizes, but each populated size keeps its own group and all groups from one submit are created atomically. Sales, Digikala receivable, fees, account entries, payments, and unrelated stock events must remain untouched.

Important V59 Takvin-purchase rule: the active `/takvin/` Excel-style purchase page represents supplier debt in `ExcelManualSetting(key="takvin_debt")` and physical goods in Takvin HOME `StockBalance` plus exact `InventoryMovement.PURCHASE`. Saving a purchase must apply both sides once. Do not use a second Account.TAKVIN purchase ledger in this page's path.

Important V60 selling-price rule: Darma/Takvin selling-price changes are dated defaults, not historical rewrites. `SaleLine.sale_price` is frozen once saved. New manual or Digikala-imported rows use `sale_price_for(product_size, SaleDay.date)`. A future price must never be copied into today's legacy ProductSize default merely because it was scheduled today.

Important V60 elastic-payment rule: one BusinessPayment may contain many elastic colors, each with independent 16/25 quantity and unit price, while retaining one actual-paid amount. The full physical purchase payload lives in the V14 purchase ledger and edit/delete must preserve guarded atomic reverse semantics.

After these, read `UI_SAFETY_V37.md` through `UI_SAFETY_V47.md`, then current `core/urls.py`, exact active source files, and older handoff docs last.

When older docs conflict with this directory or current active code, the later explicit business-rule document + current active code wins.

The latest numerically recorded production checkpoint is now V65 SAFE MODE, confirmed by the user's posted final invariant block on 2026-09-07. V46 through V60 must not be called fully production-confirmed without their successful server output markers. V49 does have direct behavioral confirmation from the user that the new KHORSHID -> HOME transfer worked and was "عالی", but that is not the same as a preserved full invariant success block. V55 requires both `SUCCESS: DARMA COST RULE V55 DEPLOYED` and `SUCCESS: DARMA COST SHAHRIVAR V55 REPAIR APPLIED`; V56 requires `SUCCESS: DARMA INVENTORY PAGE COST V56 DEPLOYED`; V57 requires `SUCCESS: RETURNS REPORT EDIT DELETE V57 DEPLOYED`; V58 requires `SUCCESS: RETURNS MULTI-SIZE V58 DEPLOYED`; V59 requires `SUCCESS: NOVANI COST RULE + TAKVIN PURCHASE V59 DEPLOYED`, and when missing today's purchase stock exists also `SUCCESS: TODAY TAKVIN PURCHASE STOCK V59 REPAIRED`; V60 requires `SUCCESS: SALE PRICE + ELASTIC MULTI V60 DEPLOYED`. V65 safe mode requires `SUCCESS: DIGIKALA ZERO GUARD V65 SAFE MODE DEPLOYED`; that marker confirms notification/read-only mapping only and does not authorize Digikala writes.

Latest confirmed numeric production snapshot:

```text
CAPITAL=5916084564
MELLAT=0
MOFID=24731000
FINISHED=1186669000
RAW=2807366700
DIGI=940899364
DIA=497000
TAKVIN_DEBT=65880000
DARMA_QTY=11432
TAKVIN_QTY=1429
NOVANI_QTY=3630
SALES=484
PAYMENTS=9
RECEIPTS=6
RAW_ROWS=53
MOVEMENTS=5225
TAKVIN_PURCHASES=10
```

This V65 deployment-boundary snapshot is continuity data, not a reset target.

Standing rule: after every important change update context; after every confirmed successful deployment update the live checkpoint with actual server output.
