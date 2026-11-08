#!/usr/bin/env bash
# V142: standalone Tapsi Shop. No database or historical ledger mutations.
# Requires production already on V141, with Tapsi schema available.
set -euo pipefail
cd /opt/darma-general
BASE=6ce92845450328a3d6482a0d4b81f22d3958bb60
BRANCH=v142-standalone-tapsi-shop
fail(){ echo "STOP: $*" >&2; exit 1; }
echo "=== V142 STANDALONE TAPSI SHOP ==="
[[ "$(git branch --show-current)" == "$BRANCH" ]] || fail "Wrong branch"
git merge-base --is-ancestor "$BASE" HEAD || fail "V141 parent baseline not preserved"
git diff --quiet -- . ':(exclude)Caddyfile' || fail "Unexpected local tracked source changes"
git diff --cached --quiet -- . ':(exclude)Caddyfile' || fail "Unexpected staged changes"
git diff --quiet "$BASE"..HEAD -- core/finance.py core/final_services.py core/sale_price_v60.py core/pricing_v60.py core/models.py core/material_report_v23.py core/material_flow.py core/inventory_valuation_v17.py Caddyfile || fail "Protected existing business source modified"
for file in $(git diff --name-only "$BASE"..HEAD); do
  case "$file" in
    .github/workflows/check-tapsi-shop-v142.yml|core/urls.py|core/tapsi_portal_v142.py|core/tapsi_views_v138.py|core/daily_views.py|core/daily_report_v8.py|core/daily_report_actions_v21.py|core/test_tapsi_shop_v138.py|templates/base.html|templates/core/sale_brand_v45.html|templates/core/daily_report_v21.html|templates/core/tapsi_shop_v142.html|core/static/core/tapsi_portal_v142.css|core/static/core/tapsi_portal_v142.js|server_tapsi_shop_v142.sh) ;;
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
BACKUP="backups/pre-v142-standalone-tapsi-$(date +%Y%m%d-%H%M%S).sql"
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
TMP=$(mktemp -d /tmp/tapsi-v141.XXXXXX)
trap 'rm -rf "$TMP"' EXIT
docker compose exec -T web python manage.py shell -c "$AUDIT" | grep -E "$PATTERN" > "$TMP/before" || fail "Baseline audit failed"
[[ "$(wc -l < "$TMP/before")" -eq 17 ]] || fail "Incomplete audit"
echo "=== BUILD CANDIDATE: DO NOT RESTART LIVE SERVICES ==="
docker compose build web || fail "Candidate build failed (live web unchanged)"
docker compose run --rm --entrypoint python web manage.py check || fail "Candidate Django check failed"
docker compose run --rm --entrypoint python web manage.py makemigrations --check --dry-run || fail "Unexpected migration drift"
docker compose run --rm --entrypoint python web manage.py shell -c "from django.db.migrations.recorder import MigrationRecorder; assert ('core','0022_tapsi_shop_v138') in MigrationRecorder.Migration.objects.values_list('app','name'), 'V139 Tapsi tables not installed'; print('TAPSI_SCHEMA=READY')" || fail "Required existing Tapsi schema missing"
docker compose run --rm --entrypoint python web manage.py shell -c "from django.urls import reverse; assert reverse('tapsi_home') == '/tapsi-shop/'; assert reverse('tapsi_hub_create') == '/tapsi-shop/orders/create/'; print('V142_STANDALONE_ROUTES=READY')" || fail "Standalone routes missing in candidate"
[[ "$(sha256sum Caddyfile | awk '{print $1}')" == "$CADDY_BEFORE" ]] || fail "Caddyfile checksum drift"
echo "=== NO SEED OR DATABASE MUTATION IN V142 ==="
echo "=== SWITCH ONLY WEB CONTAINER ==="
docker compose up -d --no-deps --no-build --force-recreate web || fail "Web restart failed"
docker compose exec -T web python manage.py check || fail "Live Django check failed"
docker compose exec -T web python manage.py shell -c "from django.urls import reverse; assert reverse('tapsi_home') == '/tapsi-shop/'; assert reverse('material_block_inline',args=[7]) == '/material-report/7/inline/'; print('STANDALONE_TAPSI_AND_PRODUCTION_ROUTES=OK')" || fail "Required routes missing"
docker compose exec -T web python manage.py shell -c "$AUDIT" | grep -E "$PATTERN" > "$TMP/after" || fail "Live audit failed"
diff -u "$TMP/before" "$TMP/after" || fail "Protected financial or stock data changed during deployment"
[[ "$(sha256sum Caddyfile | awk '{print $1}')" == "$CADDY_BEFORE" ]] || fail "Caddyfile changed"
echo "V142_STANDALONE_TAPSI=OK"
echo "V142_NO_RESEED_OR_MIGRATION=OK"
echo "EXISTING_BUSINESS_HASHES=UNCHANGED"
echo "CAPITAL_TAPSI_RECEIVABLE=PRESERVED"
echo "BACKUP=$BACKUP"
docker compose ps
