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
