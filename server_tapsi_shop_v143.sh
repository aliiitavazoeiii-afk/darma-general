#!/usr/bin/env bash
# V143: stand-alone Tapsi accounting; preserve prior orders with VAT=0 and new VAT=10%.
# Requires deployed V142. Backup, schema migration and exact historical hash audit.
set -euo pipefail
cd /opt/darma-general
BASE=87192945fa8ca1ef5bc84a748eadf9a0e3f52d59
BRANCH=v143-tapsi-jalali-calculator-monthly
fail(){ echo "STOP: $*" >&2; exit 1; }
echo "=== V143 TAPSI JALALI / CALCULATOR / MONTHLY VAT ==="
[[ "$(git branch --show-current)" == "$BRANCH" ]] || fail "Wrong branch"
git merge-base --is-ancestor "$BASE" HEAD || fail "Deployed V142 ancestor not preserved"
git diff --quiet -- . ':(exclude)Caddyfile' || fail "Unexpected local tracked source changes"
git diff --cached --quiet -- . ':(exclude)Caddyfile' || fail "Unexpected staged changes"
git diff --quiet "$BASE"..HEAD -- core/finance.py core/final_services.py core/sale_price_v60.py core/pricing_v60.py core/material_report_v23.py core/material_flow.py core/inventory_valuation_v17.py Caddyfile || fail "Protected existing business source modified"
for file in $(git diff --name-only "$BASE"..HEAD); do
  case "$file" in
    .github/workflows/check-tapsi-shop-v143.yml|core/models.py|core/migrations/0023_tapsi_commission_vat_v143.py|core/tapsi_shop_v138.py|core/tapsi_portal_v142.py|core/test_tapsi_shop_v138.py|templates/core/tapsi_shop_v142.html|core/static/core/tapsi_portal_v142.css|core/static/core/tapsi_portal_v142.js|core/static/core/tapsi_calculator_v143.js|server_tapsi_shop_v143.sh) ;;
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
BACKUP="backups/pre-v143-tapsi-vat-$(date +%Y%m%d-%H%M%S).sql"
docker compose exec -T db pg_dump -U "$DB_USER" "$DB_NAME" > "$BACKUP" || fail "DB backup failed"
[[ -s "$BACKUP" ]] || fail "Empty backup"
echo "BACKUP=$BACKUP"
AUDIT='from django.apps import apps
from hashlib import sha256
names=["StockBalance","InventoryMovement","SaleDay","SaleLine","ProductCode","ProductSize","ProductComposition","RawMaterialStock","MaterialReportBlock","MaterialReportConsumption","MaterialReportOutputApplied","AppSetting","AccountEntry","BusinessPayment","TapsiOrder","TapsiOrderItem","TapsiStockAllocation"]
for name in names:
 model=apps.get_model("core",name)
 cols=[f.attname for f in model._meta.concrete_fields if not (name=="TapsiOrder" and f.attname=="vat_percent")]
 digest=sha256()
 for row in model.objects.order_by("pk").values_list(*cols).iterator():
  digest.update(repr(row).encode("utf-8"))
  digest.update(b"\\n")
 print(name+"="+digest.hexdigest())'
PATTERN='^(StockBalance|InventoryMovement|SaleDay|SaleLine|ProductCode|ProductSize|ProductComposition|RawMaterialStock|MaterialReportBlock|MaterialReportConsumption|MaterialReportOutputApplied|AppSetting|AccountEntry|BusinessPayment|TapsiOrder|TapsiOrderItem|TapsiStockAllocation)='
TMP=$(mktemp -d /tmp/tapsi-v143.XXXXXX)
trap 'rm -rf "$TMP"' EXIT
docker compose exec -T web python manage.py shell -c "$AUDIT" | grep -E "$PATTERN" > "$TMP/before" || fail "Baseline audit failed"
[[ "$(wc -l < "$TMP/before")" -eq 17 ]] || fail "Incomplete audit"
docker compose exec -T web python manage.py shell -c "from core.models import TapsiOrder; print('COUNT='+str(TapsiOrder.objects.count()))" | grep '^COUNT=' > "$TMP/orders-before" || fail "Baseline Tapsi order count failed"
echo "=== BUILD CANDIDATE: DO NOT RESTART LIVE SERVICES ==="
docker compose build web || fail "Candidate build failed (live web unchanged)"
docker compose run --rm --entrypoint python web manage.py check || fail "Candidate Django check failed"
docker compose run --rm --entrypoint python web manage.py makemigrations --check --dry-run || fail "Unexpected migration drift"
docker compose run --rm --entrypoint python web manage.py shell -c "from django.db.migrations.recorder import MigrationRecorder; assert ('core','0022_tapsi_shop_v138') in MigrationRecorder.Migration.objects.values_list('app','name'), 'V139 Tapsi tables not installed'; print('TAPSI_SCHEMA=READY')" || fail "Required existing Tapsi schema missing"
docker compose run --rm --entrypoint python web manage.py migrate core 0023_tapsi_commission_vat_v143 --plan || fail "VAT migration plan invalid"
docker compose run --rm --entrypoint python web manage.py shell -c "from django.urls import reverse; assert reverse('tapsi_home') == '/tapsi-shop/'; print('V143_TAPSI_ROUTES=READY')" || fail "Tapsi route missing in candidate"
[[ "$(sha256sum Caddyfile | awk '{print $1}')" == "$CADDY_BEFORE" ]] || fail "Caddyfile checksum drift"
echo "=== APPLY ONLY VAT SNAPSHOT SCHEMA MIGRATION (HISTORICAL DEFAULT 0) ==="
docker compose run --rm --entrypoint python web manage.py migrate core 0023_tapsi_commission_vat_v143 --noinput || fail "VAT migration failed; current web remains unchanged"
echo "=== SWITCH ONLY WEB CONTAINER ==="
docker compose up -d --no-deps --no-build --force-recreate web || fail "Web restart failed"
docker compose exec -T web python manage.py check || fail "Live Django check failed"
docker compose exec -T web python manage.py shell -c "from django.db.migrations.recorder import MigrationRecorder; from core.models import TapsiOrder; from django.urls import reverse; assert reverse('tapsi_home')=='/tapsi-shop/'; assert MigrationRecorder.Migration.objects.filter(app='core',name='0023_tapsi_commission_vat_v143').exists(); assert not TapsiOrder.objects.exclude(vat_percent=0).exists(), 'Old rates changed'; print('V143_VAT_AND_ROUTES=OK')" || fail "Live Tapsi schema or rates invalid"
docker compose exec -T web python manage.py shell -c "$AUDIT" | grep -E "$PATTERN" > "$TMP/after" || fail "Live audit failed"
diff -u "$TMP/before" "$TMP/after" || fail "Protected financial or stock data changed during deployment"
docker compose exec -T web python manage.py shell -c "from core.models import TapsiOrder; print('COUNT='+str(TapsiOrder.objects.count()))" | grep '^COUNT=' > "$TMP/orders-after" || fail "Post-upgrade order count failed"
diff -u "$TMP/orders-before" "$TMP/orders-after" || fail "Tapsi order count changed"
[[ "$(sha256sum Caddyfile | awk '{print $1}')" == "$CADDY_BEFORE" ]] || fail "Caddyfile changed"
echo "V143_JALALI_CALCULATOR_MONTHLY=OK"
echo "V143_HISTORIC_VAT=0_NEW_VAT=10_PERCENT_ON_COMMISSION"
echo "EXISTING_BUSINESS_HASHES=UNCHANGED"
echo "CAPITAL_TAPSI_RECEIVABLE=PRESERVED"
echo "BACKUP=$BACKUP"
docker compose ps
