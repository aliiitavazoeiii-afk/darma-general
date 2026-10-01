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

## Current authoritative development line

`v102-finance-hub-consolidated`

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
