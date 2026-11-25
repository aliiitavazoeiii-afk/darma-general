#!/usr/bin/env bash
# V153: only date-scoped stripe01 profit defaults. No migrations, repricing,
# inventory updates, data backfill, or catalog mutation.
set -euo pipefail
cd /opt/darma-general
BASE=d20ac82f3a215525aa35835df1721520ae5d61d6
BRANCH=v153-stripe01-azar5-10-profit
fail(){ echo "STOP: $*" >&2; exit 1; }
echo "=== V153 DATE-SCOPED STRIPE01 PROFIT DEPLOY ==="
[[ "$(git branch --show-current)" == "$BRANCH" ]] || fail "Wrong git branch"
git merge-base --is-ancestor "$BASE" HEAD || fail "V151 base missing"
git diff --quiet -- . ':(exclude)Caddyfile' || fail "Dirty working tree"
git diff --cached --quiet -- . ':(exclude)Caddyfile' || fail "Staged changes"
for f in $(git diff --name-only "$BASE"..HEAD); do
  case "$f" in
    core/stripe_01_v151.py|core/sale_price_v60.py|core/finance.py|core/cost_accounting_v14.py|core/daily_order_import_v12.py|core/daily_order_import_v23.py|core/excel_sales.py|core/test_stripe_01_profit_v153.py|.github/workflows/check-stripe-01-profit-v153.yml|server_stripe_01_profit_v153.sh) ;;
    *) fail "Out-of-scope change: $f" ;;
  esac
done
[[ -s .env ]] || fail ".env missing"
docker compose config -q || fail "Invalid docker compose configuration"
docker compose ps --status running web | grep -q web || fail "Web is not running"
docker compose ps --status running db | grep -q db || fail "DB is not running"
CADDY_BEFORE=$(sha256sum Caddyfile | awk '{print $1}')
set -a
. ./.env
set +a
mkdir -p backups
BACKUP="backups/pre-v153-stripe01-$(date +%Y%m%d-%H%M%S).sql"
docker compose exec -T db pg_dump -U "$DB_USER" "$DB_NAME" > "$BACKUP" || fail "Backup failed"
[[ -s "$BACKUP" ]] || fail "Backup empty"
echo "BACKUP=$BACKUP"

AUDIT='from django.apps import apps
from hashlib import sha256
names=["StockBalance","InventoryMovement","SaleDay","SaleLine","ProductCode","ProductSize","ProductComposition","RawMaterialStock","MaterialReportBlock","MaterialReportConsumption","MaterialReportOutputApplied","MaterialReportFabricTransfer","AppSetting","AccountEntry","BusinessPayment","DigikalaSettlement","TapsiOrder","TapsiOrderItem","TapsiStockAllocation","Account","ExcelManualRow","MoneyMovement","TapsiPriceRule","WholesaleCustomer","WholesaleInvoice","TailorBalanceEntry"]
for name in names:
 model=apps.get_model("core",name)
 cols=[f.attname for f in model._meta.concrete_fields]
 digest=sha256()
 for row in model.objects.order_by("pk").values_list(*cols).iterator():
  digest.update(repr(row).encode("utf-8"))
  digest.update(b"\\n")
 print(name+"="+digest.hexdigest())'
PATTERN='^(StockBalance|InventoryMovement|SaleDay|SaleLine|ProductCode|ProductSize|ProductComposition|RawMaterialStock|MaterialReportBlock|MaterialReportConsumption|MaterialReportOutputApplied|MaterialReportFabricTransfer|AppSetting|AccountEntry|BusinessPayment|DigikalaSettlement|TapsiOrder|TapsiOrderItem|TapsiStockAllocation|Account|ExcelManualRow|MoneyMovement|TapsiPriceRule|WholesaleCustomer|WholesaleInvoice|TailorBalanceEntry)='
TMP=$(mktemp -d /tmp/darma-v153.XXXXXX)
trap 'rm -rf "$TMP"' EXIT
docker compose exec -T web python manage.py shell -c "$AUDIT" | grep -E "$PATTERN" > "$TMP/before" || fail "Before audit failed"
[[ "$(wc -l < "$TMP/before")" -eq 26 ]] || fail "Incomplete baseline audit"
echo "=== BUILD WEB (LIVE CONTAINERS STILL RUNNING) ==="
docker compose build web || fail "Candidate build failed"
docker compose run --rm --entrypoint python web manage.py check || fail "Django candidate check failed"
docker compose run --rm --entrypoint python web manage.py makemigrations --check --dry-run || fail "Migration drift"
docker compose run --rm --entrypoint python web manage.py migrate --check --noinput || fail "Pending migrations"
docker compose run --rm --entrypoint python web manage.py configure_stripe_01_v151 --verify || fail "V151 SKU not registered at 139000/67000 baseline"

PROBE='from datetime import date
from core.models import ProductSize
from core.sale_price_v60 import sale_price_for
from core.finance import digikala_fee_for_unit
from core.stripe_01_v151 import stripe01_unit_cost_for
ps=ProductSize.objects.select_related("product__brand","size").filter(product__brand__name="دارما",product__code="rahrah-01",size__name="XL",active=True).first()
assert ps is not None, "Stripe01 XL missing"
for day,price,cost,fee in [
 (date(2026,11,25),139000,67000,57677),
 (date(2026,11,26),162500,76000,61038),
 (date(2026,12,1),162500,76000,61038),
 (date(2026,12,2),139000,67000,74496)]:
 assert sale_price_for(ps,day)==price,(day,"price")
 assert stripe01_unit_cost_for(day,"دارما","rahrah-01",ps.unit_cost)==cost,(day,"cogs")
 assert digikala_fee_for_unit(price,day,product_code="rahrah-01",brand_name="دارما")==fee,(day,"fee")
print("V153_PROMO_BOUNDARIES=OK")'
docker compose run --rm --entrypoint python web manage.py shell -c "$PROBE" || fail "V153 candidate promo probe failed"
[[ "$(sha256sum Caddyfile | awk '{print $1}')" == "$CADDY_BEFORE" ]] || fail "Caddyfile changed"
echo "=== RECREATE WEB ONLY ==="
docker compose up -d --no-deps --no-build --force-recreate web || fail "Web restart failed"
docker compose exec -T web python manage.py check || fail "Live web check failed"
docker compose exec -T web python manage.py shell -c "$PROBE" || fail "Live promo probe failed"
docker compose exec -T web python manage.py shell -c "$AUDIT" | grep -E "$PATTERN" > "$TMP/after" || fail "After audit failed"
diff -u "$TMP/before" "$TMP/after" || fail "Financial/inventory rows changed; investigate"
[[ "$(sha256sum Caddyfile | awk '{print $1}')" == "$CADDY_BEFORE" ]] || fail "Caddyfile changed after restart"
echo "V153_STRIPE01_PROFIT=OK"
echo "V153_FINANCIAL_AND_STOCK_DATA=UNCHANGED"
echo "V153_NO_DATABASE_MIGRATIONS=YES"
echo "BACKUP=$BACKUP"
docker compose ps
