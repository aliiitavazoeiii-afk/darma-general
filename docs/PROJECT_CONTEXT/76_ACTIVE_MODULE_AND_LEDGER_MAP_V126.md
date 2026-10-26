# V126 ACTIVE CODE, ROUTES, BUSINESS LEDGERS AND DATA FLOW
Last reviewed: 2026-10-26. Functional source: `v126-payment-history-filters` @ `90a79e993adced1689c70d5b0777ce2ea7f2789f`.
**The current core/urls.py is authoritative.** Many numbered older modules remain in Git but are no longer routed.

## Stack, deployment, files
- Python/Django + PostgreSQL, Docker Compose (`compose.yml`) with Gunicorn web, Caddy reverse proxy/HTTPS. Server `/opt/darma-general`, public `gozaresh.filmjadiid.ir`.
- App routes `config/urls.py` -> `core/urls.py`. Templates `templates/core`, business modules `core`, static assets `static/core`, management checks `core/management/commands`, schema versions `core/migrations`.
- Server env `.env` and actual Docker runtime secrets NEVER copy into GitHub/chat. Repository `.env.example` is merely a template.
- Source is baked into web image; `git pull` alone does not activate changed Django code. Use feature's tested guarded deploy script, not the generic first-install script or an old reset script.

## Route-to-owner table (V126 live routing)
| User surface / URL | Authoritative view | Important dependencies |
|---|---|---|
| Dashboard `/` | `excel_dashboard_v89.dashboard` | summary/graph; Digikala price monitoring moved to report V115 |
| Sales calendar `/sales/` | `daily_views.sale_calendar` | daily SaleDay management |
| Sales entry `/sales/<day_id>/...` | `sale_brand_v19`, `sale_entry_v60` | ProductSize, SaleLine, SaleSnapshot/Allocation, date pricing |
| Daily report `/sales/<day_id>/report/` | `daily_report_v8` | sale line edits/deletes via `daily_report_actions_v21` |
| Digikala `/digikala/` and children | `digikala_views_v40` | read-only API; never enable listing writes |
| Wholesale `/wholesale/` | `wholesale_v119` | `wholesale_logic_v119`, `wholesale_export_v119`, Novani HOME |
| Returns `/returns/` | `returns_v37` | standalone returns, HOME only |
| Comprehensive report `/report/` | `report_v10` | current capital, finance KPIs, pricing monitor |
| Pricing monitor `/pricing-monitor/` | `pricing_monitor_v89` | read-only sales date comparisons |
| Material report `/material-report/` | `material_report_v92.material_report` | V125 selected-month behavior; V123 unapplied metrics |
| Material report create | POST `material_report_v92` forwards to `material_report_v23.material_report` | stock not posted merely by creation |
| Material sheet save/add color `.../save/`, `.../add-model/` | `material_report_v23` | saved input/output and model keys |
| Material raw apply all `.../apply/` | `material_report_v23.material_block_apply_materials` | V123 color attribution reconciled, raw only |
| Material raw apply one `.../apply-color/` | `material_report_v23.material_block_apply_color` | `material_color_apply_v123.sync_one_color` |
| Finished output apply `.../apply-output/` | `material_report_v23.material_block_apply_output` | signed cumulative output, location, wages |
| Material raw unapply/delete | `material_report_v20` | reverse existing raw/output ledgers correctly |
| Finance hub `/finance/` | `finance_center_v97.finance_home` | 3 native cards, six KPI balances |
| Finance accounts `/finance/accounts/` | `finance_center_v97.accounts` | active person/cash/account rows |
| Payments/receipts `/payments/` | `business_tools_v91.payments` | V126 full-history read-only filters; V91 receipt filters; child template `payments_v126.html` |
| Payment POST/add/edit/delete | `business_tools_v62` | `business_tools_v60`, v22, purchase ledger, bank balances |
| Receipt POST/add/edit/delete | `business_receipts_v64` | actual Digikala/Dia receivable and Mellat |
| Price calculator `/calculator/` | `calculator_v37` | V104/V105 margin semantics, V113 production calc integration |
| Inventory landing `/inventory/` | `inventory_center_v97.inventory_home` | shortcuts for stock/material/ops |
| Finished stock `/inventory/stock/` | `inventory_v20.inventory` | V123 zero/red and 1..9/light both total and HOME |
| Add inventory color `/inventory/color-model/add/` | `inventory_v20.add_color_model` | Color and StockBalance rows created for brand/sizes |
| Raw stock `/inventory/materials/` | `inventory_center_v97.raw_materials` | RawMaterialStock / warehouse/tailor |
| Inventory operations `/inventory/operations/` | `inventory_operations_v16.inventory_operations` | transfer and counted-absolute correction |
| Directional transfer `/inventory/operations/transfer-direction/` | `inventory_transfer_v123.inventory_transfer_direction` | HOME <-> KHORSHID stock & movement ledger |
| Takvin purchasing `/takvin/` | `takvin_v5` | Takvin HOME stock + supplier debt |
| Definitions ``/settings/*` | `views`, `catalog_v5`, `product_center_v93`, `settings_product_v60` | live product codes, compositions, color sizes |
| Other `/materials/`, `/production/`, `/expenses/`, `/assets/` | `final_views` | verify actual route on each request; older/secondary pages |

## Canonical model/data relationships

### Catalog: Brand, Color, Size, ProductCode/ProductComposition/ProductSize
- Darma brand `دارما` is stock-owning finished clothing; sizes typically M/L/XL/XXL/3XL/4XL. V111 lets owner define codes, names, colors/compositions/sizes. Existing configured color rows, not hardcoded lists, are canonical for payment dropdown V124.
- Novani brand `Novani` owns one HOME bucket and wholesale; sizes S/M/L/XL/XXL/3XL in V120. Do not assume 4XL–6XL exist merely because owner wants new sizes.
- Takvin `تکوین` owns stock, separate date-effective cost rule. Anbaresh `انبارش` is sales reporting channel backed by Darma physical stock; cannot double-count as an additional asset.
- Color name/normalization may differ between 'سرمه ای', 'سرمه‌ای', 'راه راه'. Use existing `brand_colors.py` normalized legacy mapping and stable new `color:<id>` keys, not hard-coded guesses.

### Finished goods physical stock
- `StockLocation`: HOME ("خانه"), KHORSHID ("خورشید"/"انبار"). Transfers between them preserve combined stock value and capital. Sales hit HOME only under V46, potentially negative; do not automatically rescue from warehouse.
- `StockBalance`: quantities keyed by brand/color/size/location. `InventoryMovement` and `StockTransfer` carry audit reference. User's V123 two-way transfer uses existing sync to atomically debit source and credit destination.
- `InventoryAdjustment` manual physical correction means user enters new absolute count, but ledger saves actual delta; guard reverse if subsequent same-cell movements exist.
- `SaleLine`/`SaleSnapshot`/`SaleAllocation`: sale events/immutable historical economics and exact physical colors/quantities. Daily Excel replacement must not silently erase independently entered Anbaresh/Dia/manual sales. Use canonical sync and idempotent refs.
- Returns add HOME stock with NO simulated new sale/profit/Digikala receivable; V57/V58 allow guarded corrections.
- Finished valuation uses `core/inventory_valuation_v17.py` and date/current cost rules. Never independently count Anbaresh stock as owned capital.

### Raw material purchase, warehouse/tailor
- `RawMaterialStock` is physical/value per kind/material_key/variant/location plus lot provenance; fabric/elastic (16/25), WAREHOUSE vs TAILOR. Not same stock as finished KHORSHID/HOME.
- `BusinessPayment` is actual cash outflow; material purchase full payload and unit price/quantity in V14 `MoneyMovement` purchase ledger; summary/note is NOT sufficient provenance. Since V60 elastic can have multiple colors, inspect structured ledger, not only a single 'material_key'.
- **Payment amount** and **goods invoice value** are distinct. E.g. 10 kg × 2.6m=26m goods vs 25.584m actual cash: bank -25.584m, asset +26m, capital +0.416m. That old case is a teaching example, not permission to mutate history.
- Raw material transfer from warehouse to tailor remains separate from applying material consumption. `MaterialReportConsumption` per block/kind/key/variant stores aggregate **cumulative applied** consumption and controls raw stock delta, not physical delivered shorts.
- `MaterialReportColorUse` (V123 new table, migration 0021): attribution of each color's input of fabric and shared elastic to aggregate consumption; applying color twice must not double consume; conflicting legacy contributions should abort instead of guessing.
- `MaterialReportBlock.input_data` stores each color's code, fabric kg and cut; `output_data` stores saved delivery quantity per color/size (V106 has 3 internal inputs summed). Applying finished delivery writes `MaterialReportOutputApplied` and V112 output-location ledger, inventory movements plus sewing wage. This is DISTINCT from applying raw fabric.

### Material reporting: three explicitly different scopes
1. **Live current-month KPI** (`_current_unapplied_material_metrics` in `material_report_v92.py`): only sheet dates inside this Jalali month AND each color with NO raw fabric applied; five base cards plus top counts/weight/cut/delivered/stock-applied. An old month NEVER carries into current KPI.
2. **Selected archived month's SAME KPI** (V125): clicking e.g. 'صورت مهر ۱۴۰۵' calls `?report_month=1405/07` and reruns rule #1 but using Mehr dates; old archive opens, no bleed to Aban. Live recalculation, not time-frozen snapshot.
3. **Archived month's FULL output debt**: additional `_all_month_color_delivery_metrics` over ALL Darma colors/codes in that selected month, regardless of raw fabric applied. If tailor still owes goods, that remains visible after consuming raw fabric. For each color: expected cut = sum saved cut, registered delivery = sum saved output, applied finished = sum output application, shortfall=max(0,cut-registered), surplus=max(0,registered-cut). Compare NET PER COLOR across rolls then sum positive per-color shortfall, never cross-offset black against pink. Exact pink case 1500 cut, 1538 delivered, 38 surplus and possibly only 1233 actually stock applied.
- V118 older `_summarize_open_base_colors` tracks different lifetime coded-roll/weight diagnostics. Do NOT treat that routine's all-time kg or all-time rows as the current-month visible KPI.
- Previous months remain collapsed even if unfinished: V123 revoked V122's automatically carried "بازمانده ماه قبل". V125 adds accessible old-month report and restores it after saved sheet redirect.

### Finance / capital / liabilities
- Canonical `current_capital_breakdown()` shared by Comprehensive Report/Finance. Broad formula (read latest code): signed account/person assets + finished stock value + raw materials value + Digikala receivable + other assets minus Takvin debt. Dia Gallery receivable and other additions require checking current V102/V104 code; do not duplicate. **Never add wholesale invoice gross a second time if already represented in person account + physical stock movement.**
- Digikala sale: gross - commission/processing fee - historical COGS = profit, and receivable credited by gross-fee while inventory reduces by COGS. Sales retain date-specific fees/costs/snapshots. Dia Gallery separate.
- Digikala receipt transfers receivable to Mellat; ordinary transfer of owned assets should keep capital stable. Incomplete edits can break both accounts.
- V91 receipts filters allow date/source + full filtered cash sum. V126 payments filter allows dates and calculates complete `BusinessPayment.amount` all-time total independently from any filter/page; date-filtered sum is a separate number; default 100 rows PAGE ONLY.
- Payments can be from Mellat or Mofid and to individual dynamic PERSONS account, suppliers, tailor, self, Takvin. Never silently change these balances or write during GET filters.
- Pedram: one shared signed "خیاط" person account, negative means owed to tailor, positive means receivable. V121 wholesale sale to Pedram increases balance by invoice gross; later wages deduct. V119 negative posting is obsolete. Migration 0020 creates separate Novani wholesale invoices/customers/receipts, **not** normal daily sale rows.

## Critical QA command anchors (READ exact source before running)
- `check_final_baseline_v108`: stable finance/UI/business ancestor.
- `check_fabric_roll_count_v116`: V118 coded raw-FABRIC-unapplied eligibility + recorded kg audit.
- `check_material_summary_box_grid_v110`: header and roll/progress summary.
- `check_material_transfer_v123`: month restriction, only-color materials, transfers.
- `check_inventory_alert_v123`: zero strong red, <10 light, >=10 normal.
- `check_payment_colors_v124`: all currently registered Darma colors in purchase select AND parser.
- `check_material_archive_month_v125`: Mehr selection, all color delivery debts, Aban isolation.
- `check_payment_filters_v126`: ALL payment sums, inclusive Jalali range, V91 receipts stay intact.
- `check_receipt_filters_v91`: receipts filter regression.
- `check_wholesale_v119`: Novani/Pedram core wholesale unchanged.
- `repair_pedram_wholesale_v121`: sensitive, default dry-run; DO NOT use --apply without explicit authorization and exact expected gross.

## Known pitfalls to avoid
Never:
- treat material raw application as output application;
- subtract tailor goods merely by registering a cutting input;
- sum positive per-roll shortages without offsetting same-color surplus;
- let a surplus in a different color hide another color's missing delivery;
- sum applied-to-stock units as if they were the saved delivered amounts;
- carry any archived month into current-month top KPI;
- show full archive debt table only for raw-unapplied colors;
- replace historical settled invoices/stock by an aggregate 'reset';
- mix Novani stock with Darma or warehouse raw materials with KHORSHID finished stock;
- mutate posted purchase, receipt, signed tailor account or capital directly as a cosmetic fix;
- use old V119 Pedram sign rule or old V52/V53 inventory red thresholds;
- use an archived version's helper without confirming the active route;
- run migrations, SQL resets, restore baseline or payment repair automatically for a read-only UI request.
