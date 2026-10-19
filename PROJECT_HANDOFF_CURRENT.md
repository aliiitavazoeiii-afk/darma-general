# CURRENT PROJECT HANDOFF

For the authoritative detailed continuation record, read:

`docs/00_NEW_CHAT_READ_FIRST.md`

Then read every file in:

`docs/PROJECT_CONTEXT/`

in numeric order through:

- `docs/PROJECT_CONTEXT/41_PRICING_WORKDAYS_DASHBOARD_V89.md`
- `docs/PROJECT_CONTEXT/42_DAILY_COLOR_SIZE_MATRIX_V90.md`
- `docs/PROJECT_CONTEXT/43_RECEIPT_FILTERS_V91.md`
- `docs/PROJECT_CONTEXT/44_MATERIAL_MONTH_ARCHIVE_V92.md`
- `docs/PROJECT_CONTEXT/45_PRODUCT_PRICING_CENTER_V93.md`
- `docs/PROJECT_CONTEXT/46_GLOBAL_DATE_PICKER_INVENTORY_DEFAULT_V94.md`
- `docs/PROJECT_CONTEXT/47_MULTI_DELIVERY_MEHR8_ZERO_COMMISSION_V95.md`
- `docs/PROJECT_CONTEXT/48_INVENTORY_MATERIAL_CENTER_V96.md`
- `docs/PROJECT_CONTEXT/49_MATERIAL_FINANCE_CENTER_V97.md`
- `docs/PROJECT_CONTEXT/50_FINANCE_NAV_POLISH_V98.md`
- `docs/PROJECT_CONTEXT/51_FINANCE_ACCOUNTS_VISIBLE_V100.md`
- `docs/PROJECT_CONTEXT/52_FINANCE_HUB_CAPITAL_V102.md`
- `docs/PROJECT_CONTEXT/53_NATIVE_FINANCE_NAV_V103.md`
- `docs/PROJECT_CONTEXT/54_FINANCE_KPIS_CALCULATOR_V104.md`
- `docs/PROJECT_CONTEXT/55_MARGIN_CODE_SUMMARY_MATERIAL_KPIS_V105.md`
- `docs/PROJECT_CONTEXT/56_PERSON_PAYMENTS_THREE_DELIVERIES_V106.md`
- `docs/PROJECT_CONTEXT/57_FINAL_STABLE_BASELINE_V108.md`
- `docs/PROJECT_CONTEXT/58_MATERIAL_COLOR_ROLLS_SUMMARY_UI_V109.md`
- `docs/PROJECT_CONTEXT/59_COMPACT_MATERIAL_SUMMARY_BOX_GRID_V110.md`

## Current authoritative development line

`stable-final-2026-10-04`

V100 and V101 diverged from V99. V101 is **not** a superset of V100 and its restored Finance submenu conflicts with the user's final requirement.

V102 intentionally continues V100 and defines the final Finance structure:

- one direct `مالی و ابزار` sidebar destination;
- `/finance/` contains exactly three cards: Payments, Accounts, Calculator;
- Payments/Receipts logic is unchanged;
- Accounts uses the historical Comprehensive Report account sources and mutation semantics;
- the Finance hub itself does not duplicate account rows;
- the current-capital formula has one canonical implementation in `current_capital_breakdown()`; the economic formula itself is unchanged.

`PROJECT_HANDOFF.md` is preserved as older historical/forensic context and must not override newer explicit context documents or active code.

GitHub branch state is not proof of production deployment. V102 is production-confirmed only after the VPS prints:

`SUCCESS: FINANCE HUB + CAPITAL V102 DEPLOYED`


## V103 correction after V102 production

V102 was successfully deployed with PRE = PROJECTED = FINAL business-state hashes and marker:

`SUCCESS: FINANCE HUB + CAPITAL V102 DEPLOYED`

However the user reported no visible Finance navigation change. V103 fixes the presentation architecture itself: Finance is now a native direct link in `templates/base.html`, not a middleware/JavaScript transformation. The three-card Finance hub and Accounts backend from V102 remain unchanged.

V103 is production-confirmed only after:

`SUCCESS: NATIVE FINANCE NAV V103 DEPLOYED`


## V104 Finance overview + calculator

V103 was confirmed by the user as visually correct and final for native Finance navigation.

V104 keeps that navigation and:
- shares the exact six Payments balances with the Finance root through one read-only helper/template;
- improves Accounts summary-number layout;
- replaces the old calculator with target-profit pricing, direct profit calculation and live Darma/Takvin ProductSize profitability;
- leaves sale-price mutation in Product Center only;
- does not change accounting, inventory, payment or sale formulas.

V104 is production-confirmed only after:

`SUCCESS: FINANCE KPI + CALCULATOR V104 DEPLOYED`


## V105 calculator/material corrections

V105 corrects target-profit semantics to net profit / sale price, groups profitability by product code with collapsed size details, and moves/material-styles the material-report KPIs below the page title.

The average-cut KPI is Darma-only, all-history, and limited to black/white/navy/pink/cream positive saved cuts.

The requested all-page average finished-cost KPI is intentionally deferred because the canonical live cost engine includes sewing wage and the user's latest wording did not explicitly confirm whether that wage belongs in the new global KPI.

V105 is production-confirmed only after:

`SUCCESS: MARGIN + MATERIAL KPI V105 DEPLOYED`


## V106 corrected continuation after lineage mistake

V106 continues **V105 directly**. The sibling branch `v102-person-payments-three-deliveries` was mistakenly based on obsolete V101 and must never be used as an authoritative base.

V106 preserves the V103 native direct Finance link, the V104 Finance KPIs/calculator, and the V105 calculator/material KPI corrections, then adds only:
- dynamic person-account payees with atomic balance/source-account reverse semantics;
- three internal tailor-delivery boxes per existing output cell, with the existing summed target remaining authoritative.

V106 is production-confirmed only after:

`SUCCESS: V105 RESTORED + PERSON PAYMENTS + THREE DELIVERIES V106 DEPLOYED`


## V108 FINAL STABLE BASELINE

V108 is the only branch new work should continue from after production confirmation.

It starts from V106 (therefore preserving the full V104/V105 Finance/Calculator/report lineage), then locks:
- Comprehensive Report account-management boxes out of server-rendered HTML;
- native direct Finance navigation + exactly three cards;
- six Finance KPI balances;
- final V105 calculator semantics and grouped profitability;
- V106 person-account payments and three delivery inputs;
- V105 six material KPIs plus five open-work base-color cards.

Required final marker:

`SUCCESS: FINAL STABLE BASELINE V108 DEPLOYED`

After that marker, do not start future work from older V97-V107 branches.


## V109 material-report presentation continuation

Development branch: `v109-material-color-rolls-summary-ui`.

V109 is based directly on `stable-final-2026-10-04` and changes only material-report read-only summary/presentation:
- per-color open-work roll count;
- vertically stacked, larger collapsed-sheet summary text.

V108 remains the locked baseline regression and must pass during V109 deployment.

V109 is production-confirmed only after:

`SUCCESS: MATERIAL COLOR ROLLS + SUMMARY UI V109 DEPLOYED`


## V110 compact material-sheet summary

Development branch: `v110-material-summary-box-grid`.

V110 continues V109 and changes only the collapsed material-sheet summary layout:
- five horizontal desktop boxes;
- compact height close to the old layout;
- pending output status stays inside the delivery box;
- all V109 color-roll cards and V108/V106 logic are preserved.

Production confirmation marker:

`SUCCESS: COMPACT MATERIAL SUMMARY BOX GRID V110 DEPLOYED`


## V111 PRODUCT DEFINITION

Branch `v111-product-definition-catalog-sales` continues V110 directly.

A fourth "تعریف محصول" card opens the canonical product definition editor.
Code, independent title, brand, pack count, selected color quantities and sizes
are stored in ProductCode/ProductComposition/ProductSize and appear immediately
in Colors and manual Daily Sales. Existing note/sale history/stock are preserved.
Additive migration: `0018_productcode_title`. Darma->Anbaresh title mirror preserved.

Requires `check_product_definition_v111` and the prior V108/V110 regressions.
Live deployment marker:
`SUCCESS: PRODUCT DEFINITION + COLORS + DAILY SALES V111 DEPLOYED`


## V112 — Tailor output destination picker

Current feature line: `v112-tailor-delivery-destination`; based directly on V111.

The material-sheet output sync now opens one Home/Khorshid choice for Darma.
All new output differences go to that warehouse; re-syncing an already applied
number does nothing; historical applied pieces stay in their old location.
Per-location quantities are recorded separately from the authoritative
`MaterialReportOutputApplied.quantity` total. Migration: `0019_material_output_location`.
Novani remains Home only; tailor wages continue automatically.

Regression: `check_material_output_destination_v112`.
Production marker: `SUCCESS: TAILOR DELIVERY WAREHOUSE V112 DEPLOYED`.
Detailed contract: `docs/PROJECT_CONTEXT/61_TAILOR_DELIVERY_DESTINATION_V112.md`.


## V113 production unit-cost calculator
Newest line: `v113-unit-production-cost-calculator` based on V112. Adds third read-only calculator box (fabric/elastic/12-piece sewing wage). No business model or formula changes. Deploy marker: `SUCCESS: PRODUCTION UNIT COST CALCULATOR V113 DEPLOYED`. See `docs/PROJECT_CONTEXT/62_PRODUCTION_COST_V113.md`.


## V114 CLEAN SIDEBAR — PARALLEL UI BRANCH
Branch `v114-clean-icon-sidebar-navigation` based on V113. Nine direct icon nav links; production renamed in nav only; Returns now in Inventory; Digikala is a single header; Finance is called حسابداری; Definitions opens two-card landing with original setup under /settings/initial/. No DB/schema/business logic edits. Other-chat UI branches should merge carefully (especially templates/base.html). Confirm only with `SUCCESS: CLEAN ICON SIDEBAR V114 DEPLOYED`.


## V115 STABLE SIDEBAR + REPORT
Branch `v115-stable-sidebar-report-dashboard` based on V114. Starts collapsed with no full-page toggle flash; power-only collapsed logout; centered 4-column sales cards; shared six Finance KPIs and Darma pricing now in Comprehensive Report instead of Dashboard. Read-only except presentation and view context; no schema/data mutations. Parallel UI work needs deliberate merge. Deployment marker: `SUCCESS: STABLE SIDEBAR + COMPREHENSIVE REPORT V115 DEPLOYED`.


## V116 REGISTERED FABRIC ROLL COUNT
Branch `v116-fabric-roll-count-audit` on the V115 stable UI line. Five material color cards count distinct explicit fabric codes across all Darma sheets, not incomplete cut status or anonymous positive-weight rows. Uncoded sheet IDs can be audited with `check_fabric_roll_count_v116`. Existing delivered/open-work calculations and real material stock remain unchanged. Production marker `SUCCESS: FABRIC ROLL COUNT V116 DEPLOYED`. See `docs/PROJECT_CONTEXT/65_FABRIC_ROLL_COUNT_V116.md`.


## V117 continuation (2026-10-14)

Do not develop from stale V115 or either divergent V116 branch alone. Integration branch: `v117-unified-ui-fabric-count`, parent `v116-fabric-roll-count-audit` at `b794d266c044a8e0ee6826e12be1d3b572eb59eb`. This incorporates the prior `v116-smooth-rail-report-priority` UI and the Oct 14 V116 per-color explicit fabric-code roll count. Synthetic non-DB tests cover four white and pink rolls with duplicate codes, uncoded sheets, closed completed sheets, and other-brand isolation. To diagnose actual white/pink numbers on production: `docker compose exec -T web python manage.py check_fabric_roll_count_v116`; per-color distinct code maps and uncoded sheet ids printed. Do not assume physical inventory in kg equals the number of registered rolls. V117 deployment gate: `bash server_unified_ui_fabric_v117.sh`; assert PRE=PROJECTED=FINAL before calling live. No formulas, migrations, business stock or financial data altered.


## V118 clarified fabric cards

`v118-unapplied-fabric-rolls-color-weight` supersedes V117 fabric cards. User explicitly requested roll count ONLY for coded color rows whose **fabric raw-material consumption** has NOT been applied in that sheet/color. Use positive `MaterialReportConsumption(kind=FABRIC,material_key=color)` as evidence; ignore `MaterialReportOutputApplied` for eligibility. Lifetime delivered weight (kg) for each color is the sum of all saved input weights, applied and unapplied. The 3 sewing output/open work stats and all business logic remain untouched. The user did NOT deploy V117; run the V118 guarded script directly. See `docs/PROJECT_CONTEXT/66_UNAPPLIED_FABRIC_WEIGHT_V118.md`.


## V119 Novani wholesale (latest continuation)

Branch `v119-novani-wholesale` descends from V118; adds only `خرید تکوین` sidebar label plus one top-section `فروش عمده` link, standalone half-width-card invoices, customer accounts and Pedram linked tailor special handling; four-tab Excel export; safe atomic Novani HOME stock decrement with idempotent UUID; one migration `0020_novani_wholesale` for four new tables and Pedram seed; keeps all existing business formulas and material cards unchanged. See `docs/PROJECT_CONTEXT/67_NOVANI_WHOLESALE_V119.md`. Deploy script `server_novani_wholesale_v119.sh` preserves local Caddyfile and verifies legacy data hashes. Never deploy older V118 on top. Production deployment not yet confirmed.


## V120 Novani wholesale color/size matrix — latest

Latest branch `v120-wholesale-color-size-matrix`, parent V119. ONLY new wholesale invoice-entry presentation changes: pick each Novani color/model once, display all six currently supported sizes S/M/L/XL/XXL/3XL as a quantity matrix plus one price per color, submit all nonzero size cells as a single V119-compatible atomic invoice. The sidebar, existing stock/finance/Pedram ledger, historical invoice cards, Excel exports and V118 material reports are unchanged. Inherited V119 `check_wholesale_v119` was updated for matrix markers; `test_wholesale_v119` includes multiple colors/sizes atomic posting. See `docs/PROJECT_CONTEXT/68_NOVANI_COLOR_SIZE_MATRIX_V120.md`. Deploy with `server_novani_color_matrix_v120.sh` (never older script on V120). Not deployed/visually tested on VPS until user provides logs.


## V121 — Pedram signed wholesale receivable and historical repair (LATEST)

Branch `v121-pedram-receivable-fix` follows V120. **Owner correction**: the shared `خیاط` ExcelManualRow(PERSONS) uses negative=we owe Pedram, positive=Pedram owes us. Selling Novani wholesale to Pedram MUST ADD the invoice gross to that row; later applied Material Report output wages subtract from it through existing logic. Original V119/V120 subtracted gross and falsely treated gross as settled. V121 fixes new invoices (signed +gross, `tailor_deducted_amount=0`) and exposes a one-time guarded correction for old invoices. Reported existing wrong invoice: **144,384,000 toman**. To correct it relative to already wrong balance, apply +288,768,000 once, mark its old offset as zero; never recreate the sale or stock movement. `repair_pedram_wholesale_v121` defaults read-only and only applies with `--apply --expected-gross`; it is atomic/idempotent. V121 deploy script accepts old erroneous Pedram gross **0 or exactly 144384000** and stops on unexpected values. Full context: `docs/PROJECT_CONTEXT/69_PEDRAM_RECEIVABLE_V121.md`. Wholesale UI now groups all typed size counts, color prices and receipt amounts every 3 digits and uses grouped financial display. All sidebar/material/inventory/other-customer formulas untouched. Deploy `server_pedram_receivable_v121.sh` (NOT older scripts); local Caddyfile protected.


## V122 Material Production Net/Month Carryover (LATEST)

Branch `v122-material-net-current-open` follows V121. Fixes ONLY Materials Report read-side summary: net color delivery across all current Jalali-month + carried unfinished previous-month sheets using SAVED delivery output entries, rather than applied-to-inventory counts or summed positive per-sheet deficits. For two pink rolls cut 750 each with +248 / -210, registered delivery = 1538, net remaining=0, surplus=38; stock-applied count shown independently (e.g., 1233). A previous-month sheet is carried while any raw fabric color is not applied, any net cut shortfall exists, or any individual output size differs from actually applied stock; completed previous months archive. Average cut scoped to active sheets. Existing V118 lifetime color weight/unapplied coded-roll semantics unchanged. Adds V122 read-only diagnostic for real pink cut/entered/applied amounts and guarded deploy `server_material_net_open_v122.sh`. no financial/stock write handler changed or database migration. If V121 Pedram repair is still pending, V122 deploy protects existing data and stops for explicit reconciliation. See `docs/PROJECT_CONTEXT/70_MATERIAL_NET_CARRYOVER_V122.md`.


## V123 (LATEST): material current-month unapplied, color-only apply, bidirectional transfer

Branch `v123-material-color-apply-inventory-transfer`, descendant V122. USER CORRECTION: All prior Jalali month sheets ALWAYS archive collapsed, clickable to inspect, whether open or completed. Never show a `بازمانده ماه قبل` badge. Current-month upper KPIs and five Darma color summaries include **only saved colors where RAW FABRIC has not been applied**, excluding already consumed colors and every older-month record. Net roll shortage/surplus within the same color, show applied-to-stock count separately. V123 adds per-color apply buttons under the material cost/input table, for fabric and shared 16/25 elastic; migration 0021 adds only `MaterialReportColorUse` attribution table and existing global `MaterialReportConsumption` remains canonical. Per-color updates are transactional/idempotent and reject any legacy report whose old global stock use cannot be reconciled to saved source without guessing. Full material apply and full unapply remain compatible. Inventory transfer title `انتقال`; bidirectional KHORSHID (warehouse)↔HOME chooser, default warehouse→home, AJAX transfer submit keeps date/brand/size/direction in the open page, clears input only, manual browser refresh restores default; uses existing StockTransfer/InventoryMovement and source-shortage validation; bidirectional history/edit guard maintained. No sidebar or unrelated finance data changes. See `docs/PROJECT_CONTEXT/71_MATERIAL_COLOR_APPLY_BIDIRECTIONAL_TRANSFER_V123.md`, guarded installer `server_material_color_transfer_v123.sh`. Run CI V123 test DB suite before deployment; live deploy not yet confirmed.


## V124 (LATEST) — dashboard 30 monetary sales-day chart fix

Branch `v124-dashboard-chart-repair` inherits V123 and changes ONLY `core/excel_dashboard_v89.py` 30-sale-day chart selection/aggregation and `templates/core/dashboard_excel_v89.html` Chart.js presentation. V89's positive-quantity day selector admitted 0-sale_price ordinary SaleLine draft entries, causing ghost zero-revenue dates and negative commission/COGS profit bars to pull the y axis to -50m. V124 requires positive qty AND positive sale_price for ordinary-sale chart days AND chart line items; Dia Gallery positive quantity remains eligible because its canonical fixed price uses fallback even if old stored price=0. Keeps up to 30 latest REAL monetary-sale days, no-sale holidays omitted as originally required, and recalculates ONLY chart averages accordingly. Chart y-axis min is exact min(0, actual graph profit) (does not mask legitimate real loss), losses colored red, x ticks auto-skip for readability. No changes to saved sales, raw data, daily/monthly financial KPI rules, wholesale, material reports, warehouse transfer, Caddyfile or schema. Read-only audit `check_dashboard_trend_v124` prints chart days' sales/profit and dates of 0-price draft entries. Deploy `server_dashboard_chart_v124.sh`, which requires V123 migration 0021 already applied and protects business table hashes PRE=PROJECTED=FINAL. See `docs/PROJECT_CONTEXT/72_DASHBOARD_TREND_V124.md`. Not live until server logs confirm.
