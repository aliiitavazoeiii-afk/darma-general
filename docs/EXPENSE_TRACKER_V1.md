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

## Receivable semantics

A claim means somebody owes the user money. Creating an unpaid claim does not move Mellat.

A real repayment decreases the outstanding claim and increases Mellat by the same amount. Deleting that repayment reverses only its Mellat effect.

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

GitHub main is not production evidence. Production is confirmed only after the expense deployment script prints its SUCCESS marker and the user posts the output.
