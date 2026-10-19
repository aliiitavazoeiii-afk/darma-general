# V124 — Dashboard sales/profit bar-chart correction ONLY

Base branch: `v123-material-color-apply-inventory-transfer` at commit `31c81ad544f075519319efc9d6e4bdd369848371`.

## Why chart looked distorted on 1405/07/26

Screenshot showed a nearly invisible bar near end (1405/07/25), large empty below-zero region (-50,000,000 axis), and labels skipping holidays. V89's selection of last 30 sale days used **positive quantity** only. A sale line with `quantity > 0` but `sale_price == 0` qualified as a sale day although gross revenue was zero. Existing cost/commission calculations may then yield negative profit. Chart.js autoscaled the shared y axis far below zero, shrinking visible revenue/surplus bars. We cannot conclude which specific stored line caused the negative axis without live audit.

## Guarded repair

- `core/excel_dashboard_v89.py`: chart population now latest 30 days where at least one **positive-price, positive-quantity** regular or Dia Gallery line exists. Holidays/non-sale dates intentionally still omitted. Date sorting, historical gross/profit/qty aggregation, summary averages and original accounting remain unchanged. No price is automatically filled or corrected.
- `templates/core/dashboard_excel_v89.html`: show explicit positive-revenue-day rule. Dynamic shared y axis uses `min=min(0,*profit)`, so if all displayed days are nonnegative, axis starts exactly at zero; if a genuinely paid day has negative daily profit, the loss remains visible (red profit column) with scale extending only to the actual minimum rather than rounding down by a huge negative major tick. Limit x labels to readable density while all 30 bars/data remain in tooltips.
- `core/management/commands/check_dashboard_trend_v124.py`: read-only live audit prints each chart date's real sales, profit, units, `REAL_LOSS` flag, and dates of positive-count, zero-priced draft lines within the last 50 days. **No writes**.
- `core/test_dashboard_chart_v124.py`: isolated fixture covering zero-price quantity, paid day, Dia Gallery day, zero-qty day, future, chronological newest limit and persistence of original entry.
- Existing financial totals outside the chart, sale line data, profit formula, wholesale/Pedram, material reports and warehouse operations must be bit-identical; no migration and no Caddyfile changes.

## Deployment
Branch `v124-dashboard-chart-repair`. Use `bash server_dashboard_chart_v124.sh`. It requires previous isolated migration 0021 already applied; this was successfully applied in the user's earlier V123 output. It takes a backup before any web recreation, checks exact file allowlist against V123, prevents changes to existing finance and material/stock Python logic, computes protected business-table hashes using a SINGLE shared grep regex for both old/new images (fixed V123 preflight bug), runs Django and read-only dashboard/material/wholesale checks and confirms PRE = PROJECTED = FINAL before printing success. It does not re-register transfers, correct live zero-price data, or perform schema migrations.

Critical: the V123 code may not have been activated when its earlier installer stopped during a false hash mismatch. V124 includes V123 code because it is based on V123; ensure the server switches to V124 and successfully completes web recreation. Do not claim production deployment before user logs confirm it.
