# V102 — PERSON ACCOUNT PAYMENTS + THREE-PART TAILOR DELIVERIES

## Person accounts in payments

Every active `ExcelManualRow` in section `PERSONS` is exposed as a dynamic payment payee.

Payment semantics:
- Payment source (Mellat/Mofid) decreases by the paid amount using the existing V62 source-account flow.
- The selected person's row amount decreases by the same amount.
- A payment cannot make that person's balance negative.
- Edit is atomic: the old payment is reversed first, then the edited payment is applied.
- Delete is atomic: source account and person balance are restored.
- A person row referenced by historical payments cannot be deleted from Finance/Accounts, preserving edit/delete reversibility.
- Existing material, tailor, Takvin and self-payment semantics are unchanged.

## Three delivery boxes per material-report output cell

Only the **محصول تحویلی از خیاط** cells change visually.

Each existing size cell contains 3 small internal inputs:
- delivery 1
- delivery 2
- delivery 3

The outer table dimensions/columns remain unchanged.

Persistence:
- `MaterialReportBlock.output_data` remains JSON; no migration.
- The three parts are stored in `_delivery_parts[size]`.
- The legacy size key still stores the SUM of the three parts.
- Every existing downstream target, wage, pending, stock-sync and inventory formula continues to read the legacy size total.
- Historical single-value sheets render that old value in box 1; boxes 2/3 are empty.
- Example: 50 + 70 + 50 = target 170.
- Sync sequence is cumulative/idempotent: first sync +50, second sync only +70, third sync only +50.

## Regression

`python manage.py check_person_payments_three_delivery_v102`

The regression transactionally validates:
- dynamic person payee choice;
- person balance and source-account debit;
- edit reverse/reapply;
- full reverse;
- 50+70+50 = 170;
- legacy value -> box 1;
- sync adds the summed target to finished inventory;
- all test writes roll back.

## Deploy

`bash server_person_payments_three_deliveries_v102.sh`

Expected final marker:
`SUCCESS: PERSON PAYMENTS + THREE DELIVERIES V102 DEPLOYED`
