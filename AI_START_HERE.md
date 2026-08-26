# AI START HERE — DARMA GENERAL

Last updated: 2026-08-26
Repository: `aliiitavazoeiii-afk/darma-general`
Default branch: `main`
Domain: `gozaresh.filmjadiid.ir`
Server project path: `/opt/darma-general`

## 1. Read this before changing anything

This is a live Django business-management system used instead of Excel for an apparel business. The user expects the AI to edit GitHub directly and then give short copy/paste deployment commands for the VPS.

Before doing any work:

1. Read this file completely.
2. Read `PROJECT_HANDOFF.md` completely.
3. Inspect the current `main` branch files relevant to the requested change; do not rely only on old version names.
4. Do not assume code on `main` is already deployed. Confirm the live server state from user output when deployment status matters.
5. Make a rollback branch before risky changes when practical.
6. Never run destructive inventory/database reset scripts for normal changes.

## 2. Non-negotiable safety rules

- Never use `server_inventory_fix.sh` for routine changes. It is destructive and resets business data.
- Do not blindly repair Darma stock. Current Darma stock has a known historical anomaly: `دارما / طوسی / XXL / خورشید = -50`. It must remain untouched until the user supplies a fresh physical count for HOME and KHORSHID.
- Do not run `server_fix_khorshid_negative_v15.sh`; its dry-run proved the simple HOME→KHORSHID repair is unsafe because HOME had only 43 while KHORSHID was -50.
- Preserve current capital/accounting state unless the requested operation intentionally changes it. Deployment scripts should compare capital before/after where possible.
- Prefer atomic/idempotent inventory operations and explicit ledgers over inference from notes/text.
- All sale/import inventory changes must preserve brand stock invariants and rollback on mismatch.
- Existing historical SaleSnapshots are accounting history. Do not rewrite old sale snapshots merely because pricing rules change later.

## 3. Current architecture

- Django 5.2
- PostgreSQL 16 Alpine
- Gunicorn
- WhiteNoise
- Caddy HTTPS
- Docker Compose
- True-glass navy UI; do not revert the visual system.
- Jalali dates throughout business workflows.

Primary routes currently point to:

- dashboard: `core.excel_dashboard`
- sale brand selection: `core.sale_brand_v17`
- manual sales: `core.excel_sales`
- daily Digikala XLSX import: `core.daily_order_views_v8` using `core.daily_order_import_v12`
- daily report: `core.daily_report_v8`
- comprehensive report/capital: `core.report_v9`
- materials report: `core.material_report_v16`
- payments/receipts: `core.business_tools_v14`
- inventory: `core.inventory_v5`
- inventory operations: `core.inventory_operations_v15`
- rules: `core.settings_rules_v17`

See `core/urls.py` for the current source of truth.

## 4. Current important feature generations

### v9 finance

Digikala receivable is automatic. A sale increases Digikala receivable by gross minus Digikala fee. A Digikala receipt decreases receivable and increases Mellat. Capital equation is based on assets, not cash-flow events.

### v11 Darma reference reconcile

A historical Excel baseline was reconciled to 14,311 Darma shorts / 872,971,000 toman at 61,000 each. Do not rerun this old snapshot against current live stock after newer sales/production.

### v12 Darma `s3` variable-color single item

`Darma s3` is a pack-1 product whose sold color is taken from the Digikala title, not a fixed composition. Known seller-code color hints are case-sensitive:

- `s2` = کرم
- `s3` = مشکی
- `S3` = صورتی
- `s5` = سرمه‌ای
- سفید is also recognized from the title.

The title is authoritative for variable-color `s3`.

### v14 capital/cost integrity

Capital is intended to be:

`accounts/persons + finished inventory + raw materials + Digikala receivable + assets - Takvin debt`

Internal conversions/purchases must not create capital out of nowhere. Material purchases should exchange Mellat cash for raw-material inventory with zero net capital effect.

### v15 inventory diagnostics

Manual stock transfer is guarded against insufficient source stock. Read-only diagnostics exist:

- `audit_darma_stock_v15`
- `trace_negative_darma_v15`

### v16 split material/production apply

Material reports intentionally have separate effects:

1. Save form: data only; no inventory effect.
2. Apply material consumption: only fabric/elastic consumption from tailor stock.
3. Apply finished-goods receipt: only newly received shorts are added to KHORSHID.

Finished-goods receipt is cumulative/delta-based by color × size using `MaterialReportOutputApplied`:

- enter pink=100 and apply → +100
- later add black=100 while pink stays 100 and apply → +100 black only
- later change pink from 100 to 150 and apply → +50 pink only

Never re-add previously applied quantities.

### v17 Anbaresh + date-effective Takvin cost rules

Current `main` contains v17 code, but live deployment has NOT been confirmed in this handoff.

- New active brand `انبارش` is seeded by migration `0012_takvin_cost_rule_and_anbaresh.py`.
- `sale_brand_v17.py` shows brand cards ordered دارما, تکوین, انبارش.
- Anbaresh is meant to behave like another sale brand in daily reports: gross, Digikala fee, COGS, profit, packs/shorts all use the normal SaleLine flow.
- Takvin accounting cost is now date-effective via `TakvinCostRule`.
- Default seeded Takvin costs: M=108,000; L=126,000; XL=139,500; XXL=153,000.
- `settings_rules_v17.py` lets the user add a new cost set with an effective Jalali date. Old sales remain frozen via SaleSnapshot.
- `cost_accounting_v14.snapshot_sale_line()` now uses `takvin_cost_for(size, line.day.date)` for Takvin.
- `inventory_valuation_v17.finished_inventory_value_v17()` values current Takvin inventory using the current effective Takvin rule and is used by capital/report integrity logic.
- Safe deployment script: `server_anbaresh_takvin_v17.sh`.
- v17 preflight: `python manage.py check_v17_features`.

## 5. Known Darma stock anomaly — DO NOT GUESS-FIX

Read-only audit for 1405/06/01 through 1405/06/03 showed:

- day 1 Darma sold shorts: 160
- day 2: 282
- day 3: 402
- total: 844
- allocations: 844
- applied shorts: 844
- mismatches: 0

The previously questioned Darma total `821,487,000` was mathematically correct because `863,211,000` was already the post-day-1 value.

Current anomaly from that audit:

- `طوسی / XXL / HOME = 43`
- `طوسی / XXL / KHORSHID = -50`
- target-cell net = -7

The old v11 Excel snapshot itself had `طوسی / XXL = -3` total. v11 intentionally reconciled by changing HOME only while preserving KHORSHID, so an older negative KHORSHID row could survive while HOME was adjusted to make the total match. After later sales the net became -7.

The user later stated the actual physical stock should be recounted. Correct next step is NOT to repair this cell in isolation. Wait for a complete physical HOME + KHORSHID stock count and reconcile the entire Darma matrix to the physical end-of-day baseline (intended baseline: after day 3), then continue from day 4 onward.

## 6. Deployment discipline

For normal safe deployment, scripts follow this pattern:

- start/health-check DB
- pg_dump backup
- build web image
- `makemigrations --check --dry-run`
- migrate
- preflight checks
- compare capital before/after when relevant
- recreate live web
- restart Caddy
- final checks

For current v17 code, use only after deciding to deploy it:

```bash
cd /opt/darma-general
git pull --ff-only
bash server_anbaresh_takvin_v17.sh
```

Do not claim v17 is live until the user shows successful output ending in:

`SUCCESS: ANBARESH + TAKVIN PRICING V17 DEPLOYED`

## 7. User workflow expectations

- Keep UI simple and Excel-like, not ERP-heavy.
- Edit GitHub directly when asked to implement.
- Give short copy/paste VPS commands.
- Do not ask for information already available in the repo/handoff.
- Diagnose pasted deployment errors quickly and patch GitHub if needed.
- Preserve true-glass styling and mobile behavior.
- Money uses Persian thousands separator `٬`; quantities/weights use normal decimals.

## 8. Immediate handoff priorities

The next chat should first determine what the user wants to do next. Likely pending items are:

- confirm/deploy v17 (Anbaresh + Takvin dated costs) if not yet deployed;
- wait for physical Darma HOME/KHORSHID inventory counts, then create a NEW safe full-matrix reconcile baseline after 1405/06/03;
- never use the old v11 baseline for that new physical reconcile;
- verify v16 material split behavior on the live server before entering historical material reports.

For deeper history, exact numbers, rollback branches, and file map, read `PROJECT_HANDOFF.md`.
