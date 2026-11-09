#!/usr/bin/env bash
# V146: fix Tapsi order metrics/receivable and daily UI without changing sale records or inventory.
# Requires V144 accounting schema. Existing orders recalculate fees without any DB rewrite.
set -euo pipefail
cd /opt/darma-general
BASE=9b830d5521f1de1bf6467f8d37d5e7aa15a003fe
BRANCH=v146-tapsi-correct-order-fees
fail(){ echo "STOP: $*" >&2; exit 1; }
echo "=== V146 TAPSI CORRECT 0.3 PERCENT FEES AND ORDER PROFIT ==="
[[ "$(git branch --show-current)" == "$BRANCH" ]] || fail "Wrong branch"
git merge-base --is-ancestor "$BASE" HEAD || fail "V144 accounting ancestor not preserved"
git diff --quiet -- . ':(exclude)Caddyfile' || fail "Unexpected local tracked source changes"
git diff --cached --quiet -- . ':(exclude)Caddyfile' || fail "Unexpected staged changes"
git diff --quiet "$BASE"..HEAD -- core/finance.py core/final_services.py core/sale_price_v60.py core/pricing_v60.py core/material_report_v23.py core/material_flow.py core/inventory_valuation_v17.py Caddyfile || fail "Protected existing business source modified"
for file in $(git diff --name-only "$BASE"..HEAD); do
  case "$file" in
    .github/workflows/check-tapsi-shop-v145.yml|.github/workflows/check-tapsi-shop-v146.yml|core/models.py|core/migrations/0024_tapsi_insurance_infrastructure_v144.py|core/tapsi_infrastructure_v144.py|core/tapsi_shop_v138.py|core/tapsi_portal_v142.py|core/urls.py|core/test_tapsi_shop_v138.py|core/finance_center_v97.py|templates/core/finance_center_v97.html|templates/core/finance_accounts_v97.html|templates/core/_tapsi_comprehensive_v140.html|templates/core/tapsi_shop_v142.html|templates/core/tapsi_calculator_v144.html|templates/core/tapsi_monthly_v144.html|core/static/core/tapsi_portal_v142.js|core/static/core/tapsi_calculator_v143.js|core/static/core/tapsi_portal_v142.css|server_tapsi_shop_v145.sh|server_tapsi_shop_v146.sh) ;;
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
BACKUP="backups/pre-v146-tapsi-accounting-$(date +%Y%m%d-%H%M%S).sql"
docker compose exec -T db pg_dump -U "$DB_USER" "$DB_NAME" > "$BACKUP" || fail "DB backup failed"
[[ -s "$BACKUP" ]] || fail "Empty backup"
echo "BACKUP=$BACKUP"
AUDIT='from django.apps import apps
from hashlib import sha256
names=["StockBalance","InventoryMovement","SaleDay","SaleLine","ProductCode","ProductSize","ProductComposition","RawMaterialStock","MaterialReportBlock","MaterialReportConsumption","MaterialReportOutputApplied","AppSetting","AccountEntry","BusinessPayment","TapsiOrder","TapsiOrderItem","TapsiStockAllocation"]
for name in names:
 model=apps.get_model("core",name)
 cols=[f.attname for f in model._meta.concrete_fields]
 digest=sha256()
 for row in model.objects.order_by("pk").values_list(*cols).iterator():
  digest.update(repr(row).encode("utf-8"))
  digest.update(b"\\n")
 print(name+"="+digest.hexdigest())'
PATTERN='^(StockBalance|InventoryMovement|SaleDay|SaleLine|ProductCode|ProductSize|ProductComposition|RawMaterialStock|MaterialReportBlock|MaterialReportConsumption|MaterialReportOutputApplied|AppSetting|AccountEntry|BusinessPayment|TapsiOrder|TapsiOrderItem|TapsiStockAllocation)='
TMP=$(mktemp -d /tmp/tapsi-v146.XXXXXX)
trap 'rm -rf "$TMP"' EXIT
docker compose exec -T web python manage.py shell -c "$AUDIT" | grep -E "$PATTERN" > "$TMP/before" || fail "Baseline audit failed"
[[ "$(wc -l < "$TMP/before")" -eq 17 ]] || fail "Incomplete audit"
docker compose exec -T web python manage.py shell -c "from core.models import TapsiOrder; print('COUNT='+str(TapsiOrder.objects.count()))" | grep '^COUNT=' > "$TMP/orders-before" || fail "Baseline Tapsi order count failed"
echo "=== BUILD CANDIDATE: DO NOT RESTART LIVE SERVICES ==="
docker compose build web || fail "Candidate build failed (live web unchanged)"
docker compose run --rm --entrypoint python web manage.py check || fail "Candidate Django check failed"
docker compose run --rm --entrypoint python web manage.py makemigrations --check --dry-run || fail "Unexpected migration drift"
docker compose run --rm --entrypoint python web manage.py shell -c "from django.db.migrations.recorder import MigrationRecorder; assert MigrationRecorder.Migration.objects.filter(app='core',name='0024_tapsi_insurance_infrastructure_v144').exists(), 'V144 not deployed'; print('V144_SCHEMA=READY')" || fail "Required V144 schema missing"
docker compose run --rm --entrypoint python web manage.py migrate --plan || fail "Migration plan invalid"
docker compose run --rm --entrypoint python web manage.py shell -c "from django.urls import reverse; assert reverse('tapsi_home') == '/tapsi-shop/'; assert reverse('tapsi_monthly')=='/tapsi-shop/monthly/'; assert reverse('tapsi_calculator')=='/tapsi-shop/calculator/'; print('V146_TAPSI_ROUTES=READY')" || fail "Tapsi route missing in candidate"
[[ "$(sha256sum Caddyfile | awk '{print $1}')" == "$CADDY_BEFORE" ]] || fail "Caddyfile checksum drift"
echo "=== NO MIGRATIONS, NO DB WRITES; EXISTING ORDER RECEIVABLES RECALCULATED ON READ ==="
echo "=== SWITCH ONLY WEB CONTAINER ==="
docker compose up -d --no-deps --no-build --force-recreate web || fail "Web restart failed"
docker compose exec -T web python manage.py check || fail "Live Django check failed"
docker compose exec -T web python manage.py shell -c "from django.db.migrations.recorder import MigrationRecorder; from core.models import TapsiOrder; from django.urls import reverse; assert reverse('tapsi_home')=='/tapsi-shop/'; assert reverse('tapsi_calculator')=='/tapsi-shop/calculator/'; assert reverse('tapsi_monthly')=='/tapsi-shop/monthly/'; assert MigrationRecorder.Migration.objects.filter(app='core',name='0024_tapsi_insurance_infrastructure_v144').exists(); print('V146_ORDER_ACCOUNTING_AND_ROUTES=OK')" || fail "Live rates or routes invalid"
docker compose exec -T web python manage.py shell -c "$AUDIT" | grep -E "$PATTERN" > "$TMP/after" || fail "Live audit failed"
diff -u "$TMP/before" "$TMP/after" || fail "Protected financial or stock data changed during deployment"
docker compose exec -T web python manage.py shell -c "from core.models import TapsiOrder; print('COUNT='+str(TapsiOrder.objects.count()))" | grep '^COUNT=' > "$TMP/orders-after" || fail "Post-upgrade order count failed"
diff -u "$TMP/orders-before" "$TMP/orders-after" || fail "Tapsi order count changed"
[[ "$(sha256sum Caddyfile | awk '{print $1}')" == "$CADDY_BEFORE" ]] || fail "Caddyfile changed"
echo "V146_ORDER_FEES_PROFIT_AND_RECEIVABLE=OK"
echo "V146_SAVED_ORDER_ROWS_AND_STOCK=UNCHANGED"
echo "EXISTING_BUSINESS_HASHES=UNCHANGED"
echo "CAPITAL_TAPSI_RECEIVABLE=RECOMPUTED_FROM_CORRECTED_PLATFORM_FEES"
echo "BACKUP=$BACKUP"
docker compose ps
