# DARMA GENERAL ERP — AUTHORITATIVE FULL HISTORY & FINAL DECISIONS THROUGH V126
**Handoff synchronized:** 2026-10-26 / 1405/08/04
**Documentation branch:** `docs-v126-complete-handoff-1405-08`
**Functional parent:** `v126-payment-history-filters` @ `90a79e993adced1689c70d5b0777ce2ea7f2789f`
**Repository:** https://github.com/aliiitavazoeiii-afk/darma-general
**Production URL:** https://gozaresh.filmjadiid.ir
**Server checkout:** `/opt/darma-general`
**Important:** This branch contains documentation-only changes, not a new functional release. V126 was reported working by the owner in chat. It does NOT establish an independently verified VPS git SHA or a new economic snapshot. GitHub CI success establishes test success, not deployment proof.

## What the project is
A private, stateful production Django/PostgreSQL ERP for owner-managed Darma clothing manufacturing and sales, Novani production/wholesale, Takvin purchasing/sales, and Anbaresh as a sales channel backed by Darma stock. It covers product definitions, date-effective pricing/cost, daily manual + Digikala Excel sales, Digikala read-only integrations, Dia Gallery, color/size stock, raw fabrics and elastic, tailor consumption and three-way editable delivery inputs, customer/person and bank accounts, payments, receipts, returns, cost/profit calculator, current capital, historic reports and wholesale.

This is the ERP repository only. Keep unrelated standalone projects isolated; never copy their code, credentials, deployment instructions, or workflows into this system. Never put infrastructure/server secrets in a handoff.

## Final authority / avoid mixing old documents
1. Newest explicit owner instruction, with its date and corrected context.
2. Live DB physical/financial evidence and transaction ledger for a real disputed value.
3. CURRENT `core/urls.py` route, active implementation, DB schema and confirmed functional branch/commit.
4. This file and `76_ACTIVE_MODULE_AND_LEDGER_MAP_V126.md`, `77_DEPLOYMENT_AND_CHANGE_PROTOCOL_V126.md`.
5. Version-specific docs `docs/PROJECT_CONTEXT/74_PAYMENT_HISTORY_FILTERS_V126.md` back through `01...`.
6. `docs/00_NEW_CHAT_READ_FIRST.md` contains valuable earlier forensic research but was synchronized through V108; ignore its old claim that V108 is the latest line. Similarly `AI_START_HERE.md` was historically synchronized only through V37 until the documentation-only handoff branch. DO NOT obey an obsolete "latest" banner inside old files.
7. Never guess based on filenames: V23/V91/V92/V126 files coexist; current routing/extension composition decides runtime.

## Historical implementation and decisions — the actual progression

### Foundations / V18–V37 (older source of truth: context 01–15 and version timeline 12)
- Django ERP began around Excel-ledger workflows for sales, stock and assets; PostgreSQL stores operational transactions and ledgers. Never treat an Excel physical baseline as timeless.
- V18/V20 corrected historical Darma HOME/KHORSHID physical inventory; V27 strict Digikala title resolution; V28 exposed material purchase provenance issues; V30/V30B/V31/V32 conducted specific sales reset/re-entry and end-of-31-Mordad/day-3-Shahrivar physical reconciliation. These are **historical one-time events**, not routine jobs.
- Existing errors taught critical lessons: never blindly rerun a reset; transaction.atomic failures can rollback earlier printed progress; never equate a latest purchase note with complete aggregate raw-material provenance; never resolve capital discrepancy by force-setting capital.
- V33–V35 isolated Novani material output from Darma stock, fixed output sew-wage application, enabled two-way editing/reducing applied output via saved target versus applied ledger, guarded negative reverse if stock absent, and corrected reverse-model cut display. Novani example historically 3,630 units, 110,000 toman per dozen sewing. DO NOT reapply the example as current data.
- V36 rejected inline daily returns and regrouped Comprehensive Report visually; V37 gave returns their own page and built profit/price calculator. Existing SaleSnapshot and sale allocations keep historical pricing/cost stable.

### V38–V65
- V38/V39 navy glass UI, company logo, typography and mobile layout; UI-only changes must never change profit/accounting.
- V40–V44 read-only Digikala API, order/product/package/warehouse interfaces and fulfillment corrections. Do not activate seller-side writes.
- V45 Dia Gallery is distinct Darma sales channel and receivable; document says fixed 71,000 toman/unit at creation; confirm any current price rule in active code before touching it.
- **V46 authoritative supersession:** all Darma-backed sales consume HOME only, even if negative; KHORSHID changes **only through a separately recorded manual transfer**. Earlier context 01 says auto-transfer could cover HOME, but V46 REVOKED that. Do not resurrect automatic KHORSHID -> HOME sales transfers.
- V47 theme experiments; V48 fixed daily report render bug; V49/V50 introduced batch transfer and absolute counted inventory correction. Blank correction quantities mean untouched; explicitly entered zero means set stock zero, with movement-delta audit.
- V51 strictly guarded reversal of manual inventory adjustment only if no later movement on the cell; standalone returns not the same operation.
- V52/V53 low-stock UI thresholds were later **superseded by V123**: strong red is now **exact zero** and soft red is **below ten** in both HOME and total cells. No old 30/50/100 thresholds or historical model exemptions.
- V54 safe sale-day delete reverses genuine linked effects; V55/V56 single date-effective Darma per-piece cost and correct inventory valuation; V57/V58 return edit/delete and multi-size forms; V59 Novani date-effective cost and Takvin purchase's HOME-stock-and-debt atomic posting; V60 date-effective Darma/Takvin sale pricing and multi-color elastic purchases.
- V65 Telegram zero-transition alerts were safe preview/read-only for Digikala; never enable Digikala seller writes as a side effect.

### V88–V108 (large UI/account/finance consolidation)
- V88/V89 read-only price monitoring and dashboard comparison; V90 daily color-size matrix; V91 receipts date/source filter and full filtered receipts total (must not break); V92 Jalali month archives originally hide older sheet lists.
- V93 Product Pricing Center; V94 shared Jalali picker/inventory date; V95 three-delivery and Digikala zero commission handling; V96 raw-material center; V97 finance material/account screens; V98 layout polish; V100 accounts visible; V101/V100 branches diverged.
- **V102 decision:** the Finance root is **exactly three cards**: دریافتی‌ها و پرداختی‌ها, حساب‌ها, محاسبه‌گر. Native `/finance/` and `/finance/accounts/`. Do not revert to V101's redundant sidebar/account boxes or duplicated capital calculations.
- V103 direct native Finance nav link (NOT JS injection). V104 shared six Finance KPI balances + calculator. V105 target profit in the price calculator means **net profit / selling price** (sale margin), not profit/cost; output profitability grouped by code. V106 dynamic person-account payees with atomic reverse semantics and three editable deliveries per finished-output cell; their sum is the canonical saved delivery quantity.
- **V108 stable-final-2026-10-04** consolidated the complete V106->V105->V104 ancestry. Older branches V97–V107 and especially erroneously based V106 sibling branch must not become a new base.

### V109–V118 (material reporting and sidebar)
- V109 five Darma base-color roll/progress cards, V110 compact five-box collapsed material-sheet summary. The 5 base keys: black/white/navy/pink/cream. V111 independent product definitions added canonical ProductCode, ProductComposition, ProductSize (migration 0018). V112 selectable Darma finished-output destination HOME/KHORSHID while Novani stays HOME (migration 0019); tailor wages follow output delta. V113 per-piece production-cost calculator.
- V114 clean icon sidebar; V115 stationary 72px rail/fixed icon/less distracting animation and Darma price monitor moved to Comprehensive Report. V116/V117 white/pink coded-roll and UI regressions were integrated.
- V118 roll eligibility: **nonempty fabric code whose same block+color has NO positive raw FABRIC consumption record**. Other colors' application irrelevant. V118 also retained a separate historical all-time input weight/kg in its diagnostic. Be careful: the final V123 *visible current-month KPI* has different scope; do not mix V118 lifetime audit with current-month display.

### V119–V121 (Novani wholesale and signed Pedram account)
- V119 standalone Novani wholesale invoices/buyers/receipts, frozen per-line qty/price, atomic debit of Novani HOME, own InventoryMovement; four-sheet Excel export; UUID/idempotent submission; migration `0020_novani_wholesale`. Not Digikala daily SaleLine or Darma stock. New sidebar wholesale entry.
- V120 color-first order entry: multiple colors, each one unit price and a six-size S/M/L/XL/XXL/3XL matrix, one atomic invoice. Do not invent 4XL/5XL/6XL support until inventory and schema are explicitly expanded.
- **V121 CORRECTION supersedes V119 Pedram sign convention**: shared signed `خیاط` ExcelManualRow(PERSONS), negative=we owe Pedram, positive=Pedram owes us. A wholesale invoice to Pedram **ADDS** full gross to this row; subsequent sewing wage deductions subtract. Old V119/V120 erroneously subtracted gross and marked invoice settled. For the documented one-off incorrectly posted 144,384,000-toman invoice, the conceptual correction relative to that wrong posting was +288,768,000 once, with invoice offset reset to zero. Do NOT rerun historical repair blindly; only approved dry-run/expected-gross safe flow. The user previously saw a diagnostic where Pedram balance did not change; the *current live DB state must be checked*, and repair scripts may require PREVIEW=0 before later deploy. Wholesale is an accounting-sensitive subsystem.

### V122–V126 (LATEST accepted workflows; where new chat should start)
- **V122** fixed material-delivery math: registered/saved delivery is NOT stock-applied output. Net shortages/surpluses ACROSS ROLLS of the SAME color before a single clamp. Pink example: two cuts 750 each, one +248, other -210 => cut 1500, delivered 1538, pending 0, surplus 38; if 1233 have been applied to finished inventory, 1233 is a separate applied amount. Never cross-net unrelated colors/brands. V122 originally carried unfinished previous months into current month — this was later **explicitly revoked by V123**.
- **V123 FINAL MONTH RULE:** previous Jalali months are always collapsed archives. Never show `بازمانده ماه قبل` or add old sheets to this-month top KPI. Active top KPI and five-color cards contain ONLY current-month sheet/colors whose **fabric has not been applied** (positive color-specific MaterialReportConsumption/FABRIC). Applied material color drops from those top KPIs even if tailoring delivery is still pending. Date scoping and color-scoping both mandatory.
- **V123 single-color material apply:** a multi-color production sheet can apply a single selected color's fabric + its share of elastic 16/25. Deduct raw material from tailor, not finished goods; other colors remain untouched. Aggregate stock consumption in MaterialReportConsumption; per-color contribution/idempotence ledger `MaterialReportColorUse` (migration `0021_material_color_use_v123`). Bulk apply updates attribution; previous legacy bulk rows reconcile only if exact and stop if ambiguity. Material-only apply never directly posts finished output/wage.
- **V123 stock transfer:** finished goods from KHORSHID ("انبار") to HOME (default) AND HOME->KHORSHID; atomic audited StockTransfer/InventoryMovement; cannot move more than source quantity; POST uses AJAX to avoid refresh and retains selected date/brand/size/direction while clearing submitted qty; actual browser reload resets defaults, no storage-backed permanent preference.
- **V123 stock-table highlights:** exact 0 strong red; 1–9 subdued red, 10+ normal (both "موجودی کل" and "موجودی خانه"); exceptional negative cells shown light, not zero-level bright. Supersedes V52/53.
- **V124:** `/payments/?section=payments` fabric-purchase color select AND edit form use all live active Darma colors configured in stock panel, not nine static options only. Keep legacy keys plus color:id for new colors; post validator must accept the same visible choices. No purchase valuation formula change.
- **V125 FINAL ARCHIVE REPORT:** clicking a closed old month such as `صورت مهر ۱۴۰۵` selects `?report_month=1405/07`, auto-opens that archive and re-creates old month's KPI using that month's raw-FABRIC-unapplied rows, without carrying it into current `آبان ۱۴۰۵`. A separate all-color monthly delivery debt table includes already fabric-applied rows whose finished sewing output remains pending. It nets each color's rolls, never different colors; live recalculation from current saved historic rows, NOT a frozen historical snapshot. Return to current month via link.
- **V126 (latest functional parent):** payment history now matches V91 receipt date-filter UX: inclusive optional Jalali from/to; apply/reset; filtered total/count; **all-time sum/count ALWAYS visible** independent of filter/page; actual cash `BusinessPayment.amount`, not invoice or stock valuation; both Mellat and Mofid. Previously only last 100 records in display; now all-history aggregate with display pages of 100; original transaction edit/delete remain unchanged. Implementation `core/business_tools_v91.py` read-only filter + `templates/core/payments_v126.html` (extends V91 receipt filter) + optional queryset in V60/V62 annotation. Source V126 received successful GitHub Actions build and owner said "خب اوکی شد" after installing; this is user's acceptance, not independently measured live economic state.

## Chronological document lookup
- 01–15: historical business, accounting, routes, ledger mapping, data/bugs, earliest stage.
- 16–39: UI, Digikala, Dia, HOME-only V46, inventory, date-effective cost, returns and Telegram guard.
- 40–57: pricing dashboard, receipts, Jalali archive, finance hub, calc and stable baseline.
- 58–66: material roll audit, header, product definitions, delivery destination, sidebar and V118 rule.
- 67–69: Novani wholesale V119/V120 and final Pedram V121 correction.
- 70–74: original V122 and superseding V123/V124/V125/V126; read newest first for final semantics.
- `76_ACTIVE_MODULE_AND_LEDGER_MAP_V126.md` and `77_DEPLOYMENT_AND_CHANGE_PROTOCOL_V126.md` are fresh practical maps.

## Confirmed vs historical vs unknown
Historical checkpoint values in `08_LIVE_STATE_AND_CHECKPOINTS.md` are **snapshots**. V65 was production-confirmed in that old document; later user acceptance and GitHub Actions confirmations are recorded in individual follow-up branches. Never claim any old fixed capital/inventory value is still current, and never silently repair it. The owner's separate 30 Mehr capital estimate may require -~700m toman due to yet-unreconciled fabric/elastic costs; that is a pending business/accounting concern in a DIFFERENT pricing-analysis repo, NOT authority to subtract anything from ERP automatically.

## Extra project isolation rule
This ERP repository has no ownership over unrelated services. Distinguish the separate Novani public website from this ERP's internal /wholesale/ accounting/stock module.

## Next AI handoff
Open `DARMA_NEW_CHAT_PROMPT_V126.md`, obey reading order, verify live branch and actual routes. For changes create a feature branch from actual verified latest functional HEAD, design test/rollback and guarded install. Do not work on the *documentation branch* as if it were a new deployed code release.
