#!/usr/bin/env bash
# V151: registered Darma stripe single-item, 4 exact colors; 13% commission only Azar 1-10.
# Requires V147 schema deployed. Full DB backup and before/after protected business hashes.
set -euo pipefail
cd /opt/darma-general
BASE=01a6fd7e697bed100a37a52a336f3d0185dfc00f
BRANCH=v151-stripe01-digikala-blackfriday
fail(){ echo "STOP: $*" >&2; exit 1; }
echo "=== V151 STRIPE 01 / COLOR & COMMISSION PREVIEW ==="
[[ "$(git branch --show-current)" == "$BRANCH" ]] || fail "Wrong branch"
git merge-base --is-ancestor "$BASE" HEAD || fail "V150 code ancestor not preserved"
git diff --quiet -- . ':(exclude)Caddyfile' || fail "Unexpected local tracked source changes"
git diff --cached --quiet -- . ':(exclude)Caddyfile' || fail "Unexpected staged changes"
git diff --quiet "$BASE"..HEAD -- core/models.py core/models_final.py core/migrations core/final_services.py core/sale_price_v60.py core/pricing_v60.py core/material_report_v23.py core/material_flow.py core/inventory_valuation_v17.py core/production_fabric_auto_v147.py core/business_receipts_v64.py core/darma_cost_v55.py core/capital_history_v87.py Caddyfile core/daily_order_import_v8.py core/daily_order_import_v23.py core/daily_order_views_v60.py core/material_report_v23.py core/material_report_v20.py core/business_tools_v62.py core/wholesale_logic_v119.py || fail "Protected existing business source modified"
for file in $(git diff --name-only "$BASE"..HEAD); do
  case "$file" in
    .github/workflows/check-stripe-01-v151.yml|core/stripe_01_v151.py|core/special_darma_products_v66.py|core/variant_sale_v12.py|core/finance.py|core/cost_accounting_v14.py|core/daily_order_import_v12.py|core/management/commands/configure_stripe_01_v151.py|core/test_stripe_01_v151.py|core/test_production_workspace_v131.py|core/test_production_overall_v137.py|core/test_production_inline_v138.py|server_stripe_01_v151.sh) ;;
    *) fail "Out-of-scope file: $file" ;;
  esac
done
[[ -s .env ]] || fail ".env missing"
docker compose config -q || fail "Docker Compose configuration invalid"
docker compose ps --status running web | grep -q web || fail "Live web not running"
docker compose ps --status running db | grep -q db || fail "Live db not running"
CADDY_BEFORE=$(sha256sum Caddyfile | awk '{print $1}')
set -a
. ./.env
set +a
mkdir -p backups
BACKUP="backups/pre-v151-stripe01-$(date +%Y%m%d-%H%M%S).sql"
docker compose exec -T db pg_dump -U "$DB_USER" "$DB_NAME" > "$BACKUP" || fail "DB backup failed"
[[ -s "$BACKUP" ]] || fail "Empty backup"
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
TMP=$(mktemp -d /tmp/darma-v151.XXXXXX)
trap 'rm -rf "$TMP"' EXIT
docker compose exec -T web python manage.py shell -c "$AUDIT" | grep -E "$PATTERN" > "$TMP/before" || fail "Baseline audit failed"
[[ "$(wc -l < "$TMP/before")" -eq 26 ]] || fail "Incomplete audit"
docker compose exec -T web python manage.py shell -c "from core.models import TapsiOrder; print('COUNT='+str(TapsiOrder.objects.count()))" | grep '^COUNT=' > "$TMP/orders-before" || fail "Baseline Tapsi order count failed"
echo "=== BUILD CANDIDATE: DO NOT RESTART LIVE SERVICES ==="
docker compose build web || fail "Candidate build failed (live web unchanged)"
docker compose run --rm --entrypoint python web manage.py check || fail "Candidate Django check failed"
docker compose run --rm --entrypoint python web manage.py makemigrations --check --dry-run || fail "Unexpected migration drift"
docker compose run --rm --entrypoint python web manage.py shell -c "from django.db.migrations.recorder import MigrationRecorder; assert MigrationRecorder.Migration.objects.filter(app='core',name='0025_tapsi_receipts_auto_fabric_v147').exists(), 'V147 schema not deployed'; print('V147_SCHEMA=READY')" || fail "V147 schema missing, deploy V147 first"
docker compose run --rm --entrypoint python web manage.py migrate --plan || fail "Migration plan invalid"
docker compose run --rm --entrypoint python web manage.py configure_stripe_01_v151 || fail "V151 product preflight failed; no catalog changes"
docker compose run --rm --entrypoint python web manage.py shell -c "from datetime import date; from core.stripe_01_v151 import PRODUCT_CODE,OFFER_START,OFFER_END,applies_to; from core.variant_sale_v12 import is_variable_color_product_code,resolve_variable_product_color; from core.finance import digikala_fee_for_unit; assert is_variable_color_product_code(PRODUCT_CODE); assert OFFER_START==date(2026,11,22) and OFFER_END==date(2026,12,1); assert applies_to(OFFER_START,'دارما',PRODUCT_CODE); assert not applies_to(date(2026,12,2),'دارما',PRODUCT_CODE); assert not applies_to(OFFER_START,'تکوین',PRODUCT_CODE); assert resolve_variable_product_color(PRODUCT_CODE,'شورت اسلیپ زنانه دارما مدل راه راه 01 | XL | سرمه ای')=='راه راه'; assert digikala_fee_for_unit(139000,OFFER_START,product_code=PRODUCT_CODE,brand_name='دارما')>0; print('V151_CANDIDATE_PROMO_AND_COLOR_MAPPING=PASS')" || fail "V151 code preflight failed"
[[ "$(sha256sum Caddyfile | awk '{print $1}')" == "$CADDY_BEFORE" ]] || fail "Caddyfile checksum drift"
echo "=== NO DB MIGRATIONS OR DATA BACKFILL ==="
docker compose run --rm --entrypoint python web manage.py migrate --check --noinput || fail "Unexpected pending migrations"
echo "=== SWITCH ONLY WEB CONTAINER ==="
docker compose up -d --no-deps --no-build --force-recreate web || fail "Web restart failed"
docker compose exec -T web python manage.py check || fail "Live Django check failed"
docker compose exec -T web python manage.py configure_stripe_01_v151 || fail "V151 live product preflight failed"
docker compose exec -T web python manage.py shell -c "from core.stripe_01_v151 import PRODUCT_CODE; from core.variant_sale_v12 import is_variable_color_product_code; assert is_variable_color_product_code(PRODUCT_CODE); print('V151_LIVE_STRIPE01_CODE=OK')" || fail "V151 live product code missing"
docker compose exec -T web python manage.py shell -c "$AUDIT" | grep -E "$PATTERN" > "$TMP/after" || fail "Live audit failed"
diff -u "$TMP/before" "$TMP/after" || fail "Protected financial or stock data changed during deployment"
docker compose exec -T web python manage.py shell -c "from core.models import TapsiOrder; print('COUNT='+str(TapsiOrder.objects.count()))" | grep '^COUNT=' > "$TMP/orders-after" || fail "Post-upgrade order count failed"
diff -u "$TMP/orders-before" "$TMP/orders-after" || fail "Tapsi order count changed"
[[ "$(sha256sum Caddyfile | awk '{print $1}')" == "$CADDY_BEFORE" ]] || fail "Caddyfile changed"
echo "V151_STRIPE01_CODE=OK"
echo "V151_EXISTING_SALES_AND_STOCK=UNCHANGED"
echo "EXISTING_BUSINESS_HASHES=UNCHANGED"
echo "EXISTING_PRICES_AND_BOOKED_ORDERS_UNCHANGED=YES"
echo "NEXT_STEP: docker compose exec -T web python manage.py configure_stripe_01_v151 --apply"
echo "BACKUP=$BACKUP"
docker compose ps
