# Expense Tracker V1 — isolated branch site

Branch: `expense-tracker-v1`

Base commit: `40ba4293dcd7b05fedef33f37f70ebcbeedd8655`

This is a separate Django site carried in the same repository but deployed from a separate worktree/container.

## Business boundary

The intentional business-data bridge to DARMA General is limited to the canonical payment-source account rows via:

`core.payment_source_v63.source_row(...)`

Current linked accounts:

- `SOURCE_MELAT` → canonical Mellat account row;
- `SOURCE_MOFID` → canonical Mofid account row.

Expense tracker does not create or mutate:

- BusinessPayment
- SaleLine / SaleSnapshot / SaleAllocation
- StockBalance / InventoryMovement
- Digikala receivable / AccountEntry
- materials / production / returns
- fee/cost/valuation rules

## Expense semantics — V7 authoritative

Each `DailyExpense` stores its payment source. Historical expenses are migrated with `payment_source="melat"` because all expense cash mutations before V7 were applied to Mellat.

Create expense:

`selected_source -= expense.amount`

Edit on the same source:

`selected_source += old_amount - new_amount`

Edit while changing source:

`old_source += old_amount`

`new_source -= new_amount`

Delete expense:

`expense.payment_source += expense.amount`

All account mutations are atomic and lock the canonical source row(s). The quick-entry default is Mellat; Mofid is optional per expense.

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

The deployment regressions are rollback-only/read-only and explicitly prove:

- Mellat expense create/edit/delete still reconciles exactly;
- Mofid expense create/edit/delete affects Mofid and not Mellat;
- changing an expense source restores the old account and debits the new account exactly;
- historical unapplied claims can be deleted without changing Mellat;
- new claims debit Mellat exactly;
- repayments and delete paths reverse their exact cash effects;
- transaction search totals are scoped to the current Jalali month while previous matching months remain in the archive;
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

V4 temporarily replaced the open-receivable KPI with today's ERP gross sales. This dashboard choice was superseded by V5. The read-only revenue helper remains harmless but is no longer displayed on the home dashboard.

## Cashflow + Daily Average V5

- top dashboard KPIs are: today's expense, elapsed-month daily average, this week's expense, current Jalali month's expense;
- the daily average is `current Jalali month expense total / elapsed calendar days in the month through today`;
- zero-spend days are therefore included in the average;
- after AJAX expense entry, the average updates from the updated month total without a full page reload;
- new receivable claims debit canonical Mellat immediately;
- repayments credit Mellat;
- historical claims are preserved safely and are not retroactively debited.

## Financial Excel Export V6/V7

The reports page has an authenticated `خروجی اکسل مالی` download at:

`/reports/export.xlsx`

The generated XLSX is read-only and contains five sheets:

1. `هزینه‌ها` — every recorded expense with Jalali/Gregorian date, category, payment source, title, amount and note.
2. `گردش طلب‌ها` — claims and repayments, per-person running balance, and whether that historical row actually affected Mellat.
3. `خلاصه ماهانه` — total expenses, transaction count and calendar-day daily average for every Jalali month represented in the data.
4. `خلاصه دسته‌ها` — all-time expense totals/counts and category share.
5. `وضعیت فعلی` — Mellat balance, Mofid balance, open receivables, current-month expense/average, today's expense, overall totals, plus current receivable balance per person.

User-controlled text is protected against Excel formula injection before it is written to cells. `openpyxl` is installed only in `Dockerfile.expense`; the main ERP requirements file remains unchanged.

## Dual Account + Monthly Transactions V7 — current

- quick expense entry now has `پرداخت از` with `ملت` and `مفید`;
- default source is Mellat;
- no Mofid balance card is shown on the home dashboard;
- the selected source is stored on every expense and shown in recent/history rows;
- AJAX entry preserves the chosen source for the next rapid entry until a manual refresh;
- edit can change both amount and payment source safely;
- deleting an expense restores money to the account originally stored on that expense;
- transaction filters/search run across history, but the top `جمع نتایج` is only the current Jalali month;
- previous matching months appear as collapsed month headers with their own count and total;
- opening a historical month reveals its day groups and transaction details;
- the PWA static cache is bumped to `kharj-man-shell-v7` so the new UI assets replace old cached versions.

V7 regression command:

`python manage.py check_expense_v7 --settings=expense_site.settings`

Expected deployment marker:

`SUCCESS: EXPENSE TRACKER DUAL ACCOUNT V7 DEPLOYED`
