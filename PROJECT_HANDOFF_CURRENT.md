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

## Current authoritative development line

`v105-margin-code-summary-material-kpis`

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
