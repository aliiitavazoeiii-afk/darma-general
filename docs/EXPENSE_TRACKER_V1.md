# Expense Tracker V1 — isolated branch site

Branch: `expense-tracker-v1`

Base commit: `40ba4293dcd7b05fedef33f37f70ebcbeedd8655`

This is a separate Django site carried in the same repository but deployed from a separate worktree/container.

## Business boundary

The only intentional business-data bridge to DARMA General is the canonical Mellat account row via:

`core.payment_source_v63.source_row(SOURCE_MELAT)`

Expense tracker does not create or mutate:

- BusinessPayment
- SaleLine / SaleSnapshot / SaleAllocation
- StockBalance / InventoryMovement
- Digikala receivable / AccountEntry
- materials / production / returns
- fee/cost/valuation rules

## Expense semantics

Create expense: `Mellat -= expense.amount`

Edit expense: `Mellat += old_amount - new_amount`

Delete expense: `Mellat += deleted_amount`

All three operations are atomic and lock the canonical Mellat row.

## Receivable semantics — V5 authoritative

A claim means money has actually left the user's Mellat balance and somebody now owes that money back.

New claim:

`Mellat -= claim.amount`

Real repayment:

`Mellat += repayment.amount`

Deleting a new claim restores its Mellat debit, and deleting a repayment reverses its Mellat credit.

Historical safety: claims created before V5 did not debit Mellat. `ReceivableEntry.mellat_applied` records whether a row actually affected Mellat. Migration `0003_receivable_mellat_applied` marks historical repayments as applied and leaves historical claims unapplied, so deleting an old claim cannot incorrectly add money to Mellat.

## Initial categories

- غذا
- VPN
- کار
- ماشین
- تفریح
- روزمره

More categories can be added in the UI. Categories with existing expenses cannot be deleted; they can be deactivated.

## Isolation

Deployment target: `/opt/darma-expense`

Dedicated Compose project: `darma-expense`

Default host port: `8011`

It joins the existing database Docker network discovered at deploy time. It does not replace/recreate the ERP web container and does not edit the main Caddy configuration.

GitHub main is not production evidence. Production is confirmed only after the expense deployment script completes successfully and the user posts the output.

## Final branch audit

The branch diff from the base commit contains only expense-specific new paths plus the isolated runtime/deploy files. Existing ERP `core/`, `config/`, `compose.yml`, `Caddyfile`, `templates/core/` and `static/core/` remain byte-unchanged on this branch.

The deployment regression is rollback-only and explicitly proves:

- expense create/edit/delete debits/reconciles/restores Mellat exactly;
- historical unapplied claims can be deleted without changing Mellat;
- new claims debit Mellat exactly;
- real claim repayment credits Mellat exactly;
- deleting repayment and deleting the new claim reverse their exact cash effects;
- BusinessPayment, SaleLine, AccountEntry and inventory ledgers remain unchanged.

## UI V2 — repeated backdated expense entry

Added after the first live V1 deployment:

- upgraded dark/glass visual system and properly loaded Persian web typography;
- Jalali calendar picker on expense date;
- expense date can be changed to any earlier day, including the start of the current month;
- quick expense save uses AJAX and does not navigate or scroll the page;
- after a successful save, amount/title/note are cleared;
- selected date and selected category are intentionally preserved for the next expense;
- the selected date changes back to today's date only when the page is manually reloaded;
- Mellat and current dashboard expense KPIs update immediately after AJAX save;
- recent-expense list receives the newly saved row without page refresh.

## PWA V3 — Android install + grouped transactions

- added branded 192x192 and 512x512 PNG app icons;
- added a web app manifest with standalone display, theme/background colors and app shortcuts;
- added a root-scoped service worker that caches only expense static assets and deliberately does not cache authenticated financial HTML/API responses;
- added Android install UI using `beforeinstallprompt`;
- branded sidebar/mobile header/favicon with the same app icon;
- transaction history is grouped by day;
- today and yesterday use explicit Persian labels;
- older days show Persian weekday + Jalali date;
- each day shows its own transaction count and daily total.

Full browser PWA installation requires a secure origin (HTTPS, except localhost).

## Daily Revenue V4 — historical note

V4 temporarily replaced the open-receivable KPI with today's ERP gross sales. This dashboard choice was superseded by V5 below. The read-only revenue helper remains harmless but is no longer displayed on the home dashboard.

## Cashflow + Daily Average V5 — current

- top dashboard KPIs are: today's expense, elapsed-month daily average, this week's expense, current Jalali month's expense;
- the daily average is `current Jalali month expense total / elapsed calendar days in the month through today`;
- zero-spend days are therefore included in the average;
- after AJAX expense entry, the average updates from the updated month total without a full page reload;
- new receivable claims debit canonical Mellat immediately;
- repayments credit Mellat;
- delete paths reverse only cash effects that were actually applied;
- historical claims are preserved safely and are not retroactively debited.

Regression success marker for this revision:

`SUCCESS: EXPENSE TRACKER CASHFLOW V5 REGRESSION PASSED`
