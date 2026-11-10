#!/usr/bin/env bash
# V148: read-only production pack-cost dashboard; no models, migrations, or accounting changes.
# Requires V147 schema deployed. Full DB backup and before/after protected business hashes.
set -euo pipefail
cd /opt/darma-general
BASE=d49db327a46b2f5069dae4125579db0dd5e2e5e2
BRANCH=v148-production-pack-costs
fail(){ echo "STOP: $*" >&2; exit 1; }
echo "=== V148 PRODUCTION PACK COST REPORT / READ ONLY ==="
[[ "$(git branch --show-current)" == "$BRANCH" ]] || fail "Wrong branch"
git merge-base --is-ancestor "$BASE" HEAD || fail "V147 code ancestor not preserved"
git diff --quiet -- . ':(exclude)Caddyfile' || fail "Unexpected local tracked source changes"
git diff --cached --quiet -- . ':(exclude)Caddyfile' || fail "Unexpected staged changes"
git diff --quiet "$BASE"..HEAD -- core/models.py core/models_final.py core/migrations core/finance.py core/final_services.py core/sale_price_v60.py core/pricing_v60.py core/material_report_v23.py core/material_flow.py core/inventory_valuation_v17.py core/production_fabric_auto_v147.py core/tapsi_shop_v138.py core/business_receipts_v64.py core/darma_cost_v55.py core/capital_history_v87.py Caddyfile || fail "Protected existing business source modified"
for file in $(git diff --name-only "$BASE"..HEAD); do
  case "$file" in
    .github/workflows/check-production-pack-cost-v148.yml|core/urls.py|core/production_pack_cost_v148.py|core/test_production_pack_cost_v148.py|templates/core/production_pack_costs_v148.html|templates/core/material_report_v131.html|templates/core/material_report_overall_v137.html|server_production_pack_cost_v148.sh) ;;
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
BACKUP="backups/pre-v148-pack-cost-report-$(date +%Y%m%d-%H%M%S).sql"
docker compose exec -T db pg_dump -U "$DB_USER" "$DB_NAME" > "$BACKUP" || fail "DB backup failed"
[[ -s "$BACKUP" ]] || fail "Empty backup"
echo "BACKUP=$BACKUP"
AUDIT='from django.apps import apps
from hashlib import sha256
names=["StockBalance","InventoryMovement","SaleDay","SaleLine","ProductCode","ProductSize","ProductComposition","RawMaterialStock","MaterialReportBlock","MaterialReportConsumption","MaterialReportOutputApplied","MaterialReportFabricTransfer","AppSetting","AccountEntry","BusinessPayment","DigikalaSettlement","TapsiOrder","TapsiOrderItem","TapsiStockAllocation"]
for name in names:
 model=apps.get_model("core",name)
 cols=[f.attname for f in model._meta.concrete_fields]
 digest=sha256()
 for row in model.objects.order_by("pk").values_list(*cols).iterator():
  digest.update(repr(row).encode("utf-8"))
  digest.update(b"\\n")
 print(name+"="+digest.hexdigest())'
PATTERN='^(StockBalance|InventoryMovement|SaleDay|SaleLine|ProductCode|ProductSize|ProductComposition|RawMaterialStock|MaterialReportBlock|MaterialReportConsumption|MaterialReportOutputApplied|MaterialReportFabricTransfer|AppSetting|AccountEntry|BusinessPayment|DigikalaSettlement|TapsiOrder|TapsiOrderItem|TapsiStockAllocation)='
TMP=$(mktemp -d /tmp/darma-v148.XXXXXX)
trap 'rm -rf "$TMP"' EXIT
docker compose exec -T web python manage.py shell -c "$AUDIT" | grep -E "$PATTERN" > "$TMP/before" || fail "Baseline audit failed"
[[ "$(wc -l < "$TMP/before")" -eq 19 ]] || fail "Incomplete audit"
docker compose exec -T web python manage.py shell -c "from core.models import TapsiOrder; print('COUNT='+str(TapsiOrder.objects.count()))" | grep '^COUNT=' > "$TMP/orders-before" || fail "Baseline Tapsi order count failed"
echo "=== BUILD CANDIDATE: DO NOT RESTART LIVE SERVICES ==="
docker compose build web || fail "Candidate build failed (live web unchanged)"
docker compose run --rm --entrypoint python web manage.py check || fail "Candidate Django check failed"
docker compose run --rm --entrypoint python web manage.py makemigrations --check --dry-run || fail "Unexpected migration drift"
docker compose run --rm --entrypoint python web manage.py shell -c "from django.db.migrations.recorder import MigrationRecorder; assert MigrationRecorder.Migration.objects.filter(app='core',name='0025_tapsi_receipts_auto_fabric_v147').exists(), 'V147 schema not deployed'; print('V147_SCHEMA=READY')" || fail "V147 schema missing, deploy V147 first"
docker compose run --rm --entrypoint python web manage.py migrate --plan || fail "Migration plan invalid"
docker compose run --rm --entrypoint python web manage.py shell -c "from django.urls import reverse; from core.production_pack_cost_v148 import build_pack_cost_report; assert reverse('production_pack_costs') == '/material-report/pack-costs/'; result=build_pack_cost_report(); assert result['products_total']>=result['products_ready']; print('V148_PACK_COSTS_READ_ONLY=READY: '+str(result['products_total'])+' active products')" || fail "Pack cost report candidate failed"
[[ "$(sha256sum Caddyfile | awk '{print $1}')" == "$CADDY_BEFORE" ]] || fail "Caddyfile checksum drift"
echo "=== NO DB MIGRATIONS OR BACKFILL / ONLY WEB UI ==="
docker compose run --rm --entrypoint python web manage.py migrate --check --noinput || fail "Unexpected pending migrations"
echo "=== SWITCH ONLY WEB CONTAINER ==="
docker compose up -d --no-deps --no-build --force-recreate web || fail "Web restart failed"
docker compose exec -T web python manage.py check || fail "Live Django check failed"
docker compose exec -T web python manage.py shell -c "from django.urls import reverse; from core.production_pack_cost_v148 import build_pack_cost_report; assert reverse('production_pack_costs')=='/material-report/pack-costs/'; data=build_pack_cost_report(); assert data['products_total']>=data['products_ready']; print('V148_LIVE_PACK_COSTS=OK')" || fail "Live production cost report failed"
docker compose exec -T web python manage.py shell -c "$AUDIT" | grep -E "$PATTERN" > "$TMP/after" || fail "Live audit failed"
diff -u "$TMP/before" "$TMP/after" || fail "Protected financial or stock data changed during deployment"
docker compose exec -T web python manage.py shell -c "from core.models import TapsiOrder; print('COUNT='+str(TapsiOrder.objects.count()))" | grep '^COUNT=' > "$TMP/orders-after" || fail "Post-upgrade order count failed"
diff -u "$TMP/orders-before" "$TMP/orders-after" || fail "Tapsi order count changed"
[[ "$(sha256sum Caddyfile | awk '{print $1}')" == "$CADDY_BEFORE" ]] || fail "Caddyfile changed"
echo "V148_PRODUCTION_PACK_COSTS=OK"
echo "V148_EXISTING_SALES_PRODUCTION_STOCK=UNCHANGED"
echo "EXISTING_BUSINESS_HASHES=UNCHANGED"
echo "BILLING_PRICES_AND_ACCOUNTING_UNCHANGED=YES"
echo "BACKUP=$BACKUP"
docker compose ps
