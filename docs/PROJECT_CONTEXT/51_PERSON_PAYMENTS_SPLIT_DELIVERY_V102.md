# V102 — Person Payments + Split Tailor Deliveries + Five-Color Open Work

Branch: `v102-person-payments-split-delivery-color-progress`

## 1. Person accounts in Payments

Every active `ExcelManualRow.PERSONS` row is exposed in the existing payment payee selector using a stable key:

`person:<row_id>`

The visible label is prefixed with `شخص —` so a person account named `خیاط` is not confused with the existing special tailor workflow.

When a person payee is selected:
- the selected source account (Mellat or Mofid) is debited by the normal V62 source-account logic;
- that exact PERSONS row is decreased by the payment amount;
- editing reverses the old person/source effects before applying the new values;
- deleting restores both the source account and the person balance.

The business/accounting capital formula is not changed in V102.

Person rows referenced by a payment cannot be deleted from Finance > Accounts until the related payments are removed. Renaming is safe because payment identity is row-id based.

## 2. Three delivery installments in the existing material-report table

The outer table, columns, sizes, and sync semantics remain unchanged.

Each existing output cell now contains three small internal inputs. Example:

50 + 70 + 50 = canonical target 170

Storage remains inside the existing `MaterialReportBlock.output_data` JSON, so there is no DB migration.

For each model/size:
- `_delivery_parts[size]` stores the three entered installments;
- the existing `output_data[model][size]` stores their sum;
- all existing output sync, inventory movement, wage, pending, and monthly-report logic continue reading the canonical summed size value.

Legacy blocks that stored one total only render that old total in the first mini-box and leave boxes 2/3 empty.

## 3. Five base-color outstanding work cards

Below the existing monthly KPI row, V102 shows five cards:
- مشکی
- سفید
- سرمه‌ای
- صورتی
- کرم

Each card shows:
- expected delivery according to CUT,
- actually applied delivery,
- remaining delivery.

Only OPEN Darma work is included for that color: blocks where `cut > applied delivery`.
Completed historical sheets are excluded from these operational cards, so old completed production does not inflate the numbers.

Actual delivery is sourced from `MaterialReportOutputApplied`, not merely typed form values.

## Safety

No migrations.
No model schema changes.
Raw-material consumption formulas unchanged.
Output inventory sync formula unchanged.
Tailor wage formula unchanged.
Current capital formula unchanged.
Existing receipt/payment/material routes remain unchanged.

Deployment is production-confirmed only after:
`SUCCESS: PERSON PAYMENTS + SPLIT DELIVERY + COLOR PROGRESS V102 DEPLOYED`
