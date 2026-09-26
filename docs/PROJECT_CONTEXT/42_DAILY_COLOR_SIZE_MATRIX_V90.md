# V90 — DAILY PRODUCT / COLOR / SIZE SALES MATRIX

Prepared: 2026-09-26

## Scope

V90 is read-only for business data. It extends the existing daily sales report shown after an XLSX daily-order import.

No sale, stock, receivable, accounting, cost, price, capital or snapshot formula is changed.

## User-visible behavior

Below the existing daily sales/profit report, V90 adds a matrix:

- row identity: brand + product code + physical color;
- columns: sizes present in that day's SaleLine data;
- cell: number of physical shorts sold for that product/color/size;
- final column: row total;
- footer: total shorts for every size and grand total.

`06`, `6`, `pack6` and `pack06` are canonicalized to product code `06` in this matrix.

Dia Gallery remains in its existing separate section and is not mixed into the XLSX/SaleLine matrix.

## Physical-color source

V90 reuses the existing daily-report color-breakdown rule:

1. `SaleAllocation` is authoritative when present, because it records the physical color actually deducted from stock, including replacements.
2. Older rows without allocations fall back to the product's configured `ProductComposition`.
3. If neither source yields a color, the row is shown as `رنگ نامشخص` rather than silently disappearing.

Replacement quantities are marked in the matrix UI.

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

- `pack6/06` canonical aggregation;
- product/color/size aggregation;
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
