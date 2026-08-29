# 08 — LIVE STATE AND CHECKPOINTS

This file records confirmed production/historical checkpoints. These numbers are for continuity and forensic reconciliation. They are **not permanent targets** and must never be force-restored after legitimate later activity unless the user explicitly requests a rollback to that checkpoint.

Last synchronized: 2026-08-29 after confirmed V37 live deployment.

---

## 1. Latest confirmed live deployment: V37

User posted successful production output from:

```bash
cd /opt/darma-general
git pull --ff-only
bash server_standalone_returns_calculator_v37.sh
```

Final invariant output:

```text
CAPITAL=5441972371
FINISHED=1115731500
RAW=1994448050
DIGI=812517154
DARMA=12072
TAKVIN=1195
NOVANI=3630
SALES=202
ACCOUNT_ENTRIES=206
```

Explicit success marker:

```text
SUCCESS: STANDALONE RETURNS + CALCULATOR V37 DEPLOYED
```

Backup created by that deployment:

```text
backups/before-standalone-returns-calculator-v37-20260829-205844.sql
```

Therefore as of this handoff:

- V37 standalone returns is confirmed live;
- V37 calculator is confirmed live;
- old inline daily-report return route/box is retired;
- protected accounting/finance/material formula files passed deploy guard;
- deploy itself did not change the final economic/inventory invariants.

---

## 2. Latest confirmed feature semantics live at V37 checkpoint

### Daily report

- uses `daily_report_v8`;
- renders pre-return `daily_report_v21.html`;
- no inline return box.

### Standalone return

- `/returns/` page;
- mode color/code;
- Darma/Takvin;
- size selection;
- HOME-only positive stock effect;
- no sale/profit/Digikala/account effect.

### Calculator

- current Jalali-month realized Darma/Takvin profit-on-cost basis;
- exact current `digikala_fee_for_unit()` fee engine;
- new cost -> minimum price to preserve current margin;
- suggestion rounded upward to 1,000 toman.

### Comprehensive report

- V36 visual grouping remains active through `report_excel_v36.html`;
- calculation remains `report_v9`.

### Material report

- V22 routes / V35 template behavior active;
- Darma + Novani cumulative delivery editable both directions;
- sewing wage 110,000 per 12 delivered pieces;
- cut comparison display with reverse-model cut fix.

---

## 3. 31 Mordad capital checkpoint

User stated the correct total capital on end of 31 Mordad was:

```text
5,471,152,736 toman
```

This was used as the opening capital checkpoint for the Shahrivar forensic rebuild.

The user's separately calculated profit from start of Shahrivar through the then-entered reports was:

```text
72,012,896 toman
```

Pure opening + sale-profit arithmetic would be:

```text
5,471,152,736
+  72,012,896
=5,543,165,632
```

However the project correctly noted that other capital-changing inventory/purchase adjustments can make actual current capital differ from opening + sale profit. Never force current capital to this arithmetic without reconciling all components.

---

## 4. Digikala 31 Mordad base/reference mentioned by user

User stated a 31 Mordad Digikala receivable reference of:

```text
872,647,000 toman
```

A later audit found sale profit matched exactly and the then-current Digikala discrepancy was only around 470 toman, narrowing the major capital discrepancy away from sale-profit and Digikala formulas.

Important: the editable comprehensive-report Digikala field stores desired current total by converting it to base = desired - ledger. See accounting docs.

---

## 5. Historical Shahrivar rebuild checkpoint after days 1-3

User reset/re-entered daily sales and then stated that after entering through 3 Shahrivar, total capital was correct at:

```text
5,493,056,769 toman
```

This is a historical debugging checkpoint immediately before the requested exact physical inventory adjustment for end of day 3.

Do not assume it remains the correct current capital after subsequent physical reconciliation, material/Novani production, payments or returns.

---

## 6. Authoritative physical Darma end-of-day 3 Shahrivar baseline

Physical sheets for HOME and KHORSHID established:

```text
HOME      = 4,585 shorts
KHORSHID  = 8,890 shorts
TOTAL     = 13,475 shorts
```

Per size:

```text
M    = 1,948
L    = 3,807
XL   = 2,529
XXL  = 3,716
3XL  = 1,071
4XL  =   404
```

Per color total:

```text
مشکی          2,248
سفید          1,077
سرمه ای       2,434
صورتی         1,477
کرم           2,297
قرمز            450
زرد              110
طوسی             212
راه راه           464
راه راه طوسی    1,699
برعکس مشکی        375
برعکس سفید        347
برعکس سرمه ای     285
```

Critical corrected cells:

```text
KHORSHID / کرم / XXL  = 400
KHORSHID / قرمز / XXL = 0
HOME / کرم / 3XL      = 77
Darma total / طوسی / 4XL = 0
```

This is a historical physical truth point after day-3 sales; do not reapply day-3 sales after setting this baseline.

---

## 7. Historical pre-physical audit immediately around V18

Older audited Darma quantity:

```text
13,467 shorts
```

Physical baseline:

```text
13,475 shorts
```

Difference:

```text
+8 shorts
```

At the then-current 61,000 accounting value:

```text
+488,000 toman
```

A prior user-reported post-V18 capital was:

```text
5,485,803,435
```

and inventory total:

```text
3,129,524,600
```

These are historical continuity values only.

---

## 8. Historical 31 Mordad Darma workbook baseline

During the sales bug reconstruction, a workbook `mojodi 31 mordad.xlsx` was treated as the authoritative aggregate Darma end-of-31-Mordad starting inventory.

Totals:

```text
TOTAL = 14,864 shorts
M     = 2,109
L     = 4,096
XL    = 3,002
XXL   = 4,106
3XL   = 1,143
4XL   =   408
```

At 61,000 per short:

```text
906,704,000 toman
```

The workbook itself contained some negative cells and those were preserved as historical Excel truth instead of being arbitrarily zeroed.

The workbook did not provide HOME/KHORSHID split; the baseline implementation preserved KHORSHID and adjusted HOME so each aggregate color/size matched the workbook.

This baseline is historical and must not be applied on current production unless explicitly rebuilding from 31 Mordad again.

---

## 9. Novani current block / inventory continuity

A real Novani material-report delivery contained:

```text
مشکی   710
سفید   660
سرمه‌ای 750
صورتی  700
کرم    810
TOTAL 3,630
```

This is why the V37 invariant snapshot shows:

```text
NOVANI=3630
```

assuming no other Novani stock operations occurred between that block and the V37 deployment.

Current sewing wage for that 3,630-piece delivered block:

```text
33,275,000 toman
```

at 110,000 per 12.

---

## 10. Elastic payment #6 historical checkpoint

Diagnostic details:

```text
payment_id=6
created_at=2026-08-29 08:08:13.161618+00:00
actual paid=25,584,000
elastic16 q=5 kg, p=2,600,000/kg
elastic25 q=5 kg, p=2,600,000/kg
invoice/goods value=26,000,000
```

Capital difference from goods value - actual paid:

```text
+416,000
```

At one diagnostic moment aggregate stock showed 10/10 instead of purchase-ledger 5/5, leading to V28 forensic work. Do not infer current raw stock from that historical anomaly; V37 RAW checkpoint is the current confirmed aggregate value at handoff.

---

## 11. Current production values are mutable after handoff

The V37 checkpoint is the last value known to this documentation. As soon as the user records any new:

- sale;
- return;
- production output;
- material consumption;
- purchase;
- payment;
- Digikala receipt;
- manual account change;
- inventory adjustment;

one or more checkpoint values can legitimately change.

A new AI/chat should treat the V37 numbers as **"last known before later operations"**, not as a database constraint.

---

## 12. How to establish a new live checkpoint

For a new phase, run a read-only snapshot using the same components used in guarded deploy scripts:

```text
capital
finished inventory value
raw material total
Digikala receivable
Darma qty
Takvin qty
Novani qty
SaleLine count
AccountEntry count
```

Record the date/time and the business action boundary (e.g. "after importing 4 Shahrivar", "before new production block") so comparisons remain meaningful.
