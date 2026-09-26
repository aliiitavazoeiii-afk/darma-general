# V90 — DAILY COLOR / SIZE SALES MATRIX

Prepared: 2026-09-26

## Scope

V90 is read-only for business data. It extends the existing daily sales report shown after an XLSX daily-order import.

No sale, stock, receivable, accounting, cost, price, capital or snapshot formula is changed.

## User-visible behavior

Below the existing daily sales/profit report, V90 adds one simple matrix:

- rows: physical colors sold that day;
- columns: sizes present in that day's SaleLine data;
- cell: total number of shorts sold for that color + size across ALL products/packs/brands in the daily XLSX report;
- final column: total shorts sold for that color;
- footer: total shorts sold for each size and grand total.

There is deliberately NO product-code or brand dimension in this matrix.

Example: if multiple models/packs together sold 30 navy M shorts, the single `سرمه‌ای × M` cell is `30`.

Dia Gallery remains in its existing separate section and is not mixed into the XLSX/SaleLine matrix.

## Physical-color source

V90 reuses the existing daily-report color-breakdown rule:

1. `SaleAllocation` is authoritative when present, because it records the physical color actually deducted from stock, including replacements.
2. Older rows without allocations fall back to the product's configured `ProductComposition`.
3. If neither source yields a color, the row is shown as `رنگ نامشخص` rather than silently disappearing.

Replacement quantities may be marked on the color row, but the numeric matrix cell always represents the full sold quantity of that color/size.

## Safety / reconciliation

The matrix calculates both:

- expected shorts = sum of canonical `sale_line_metrics(...)[shorts]` for SaleLines in the report;
- physical-color total = sum of the color/size matrix.

If they differ, the daily report shows an explicit reconciliation warning. V90 does not force either number to match and does not mutate historical rows.

## Regression

Run:

```bash
python manage.py check_daily_color_size_v90
```

Expected marker:

```text
SUCCESS: DAILY COLOR-SIZE MATRIX V90 CHECK PASSED
```

The regression checks:

- same color/size is aggregated across different products and brands;
- product/brand dimensions do not leak into the matrix rows;
- replacement-color marker;
- daily report template/render;
- Telegram notification is mocked during regression;
- SaleDay and SaleLine row counts remain unchanged.

## Deployment

No migration is required.

Use:

```bash
bash server_daily_color_size_v90.sh
```

Do not call V90 production-confirmed until the VPS success marker is observed.
