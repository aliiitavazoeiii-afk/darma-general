# V107 — RESTORE FINANCE KPIs + V105 CALCULATOR

Branch: `v107-restore-finance-calculator`
Base: current direct-finance V103 line `b7b305e8f6a8a52cc97381b21a278ff3740e8d73`

## Why this exists

The direct Finance & Tools work was continued from a branch that still contained the older calculator UI. The already-built calculator work from V104/V105 existed on a separate line and was therefore missing from the current three-card Finance hub.

V107 selectively restores that later calculator/finance presentation onto the current line without replacing the newer person-payment, split-delivery, five-color material KPI, or direct finance navigation work.

## Finance & Tools

The hub remains exactly three cards:
- دریافتی‌ها و پرداختی‌ها
- حساب‌ها
- محاسبه‌گر

Above the three cards, the shared six read-only balances from V104 are restored:
- موجودی ملت
- موجودی مفید
- طلب دیجی‌کالا
- طلب Dia Gallery
- حساب خیاط
- بدهی تکوین

Payments and Finance home use the same read-only helper:
`core.finance_overview_v104.finance_kpis()`

## Restored Calculator = final V105 semantics

Two calculator panels:
1. finished cost + desired sale margin -> required selling price;
2. selling price + finished cost -> fee, net profit, sale margin, profit on cost.

Target percentage means:
`net profit / sale price * 100`

It does NOT mean profit / cost.

Canonical Digikala fee:
`core.finance.digikala_fee_for_unit()`

The exact minimum price is solved mathematically and the practical displayed recommendation rounds upward to the next 1,000 toman.

## Profitability table

Active Darma and Takvin ProductSize rows are read from the canonical current price/cost engines, then grouped by product code.

Each code summary shows average:
- current sale price
- finished pack cost
- Digikala fee
- net profit
- sale margin
- profit on cost

Clicking a code opens the size-level rows.

Sources remain:
- sale price: `sale_price_for(product_size, today)`
- Darma unit cost: `darma_cost_for(today)`
- Takvin unit cost: `takvin_cost_for(size, today)`
- fee: `digikala_fee_for_unit(price, today)`

## Preserved newer work

V107 does not replace:
- person-account payments and reverse semantics;
- three delivery mini-boxes and canonical summed output;
- five-base-color open-work material cards;
- direct Finance & Tools sidebar link;
- current account mutation semantics.

No schema migration.

## Regression

`python manage.py check_finance_calculator_v104`

Expected marker:
`SUCCESS: FINANCE KPI + CALCULATOR V104 CHECK PASSED`

V107 deployment is production-confirmed only after:
`SUCCESS: RESTORED FINANCE + CALCULATOR V107 DEPLOYED`
