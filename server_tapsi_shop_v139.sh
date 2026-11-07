#!/usr/bin/env bash
# V138 independent Tapsi Shop rollout. Run via bash in a child process.
# Existing Digikala, Takvin, production and Caddy business code unchanged.
set -euo pipefail
cd /opt/darma-general
BASE=766698ecc033c0b5baaefe871b5cbc31a9d0a5dc
BRANCH=v139-tapsi-shop-with-production-inline
fail(){ echo "STOP: $*" >&2; exit 1; }

echo "=== V139 TAPSI SHOP GUARDED RELEASE ==="
[[ "$(git branch --show-current)" == "$BRANCH" ]] || fail "Wrong branch"
git merge-base --is-ancestor "$BASE" HEAD || fail "V138 production inline-save baseline missing"
git diff --quiet -- . ':(exclude)Caddyfile' || fail "Local tracked modifications outside Caddyfile"
git diff --cached --quiet -- . ':(exclude)Caddyfile' || fail "Unexpected staged changes"
git diff --quiet "$BASE"..HEAD -- core/finance.py core/final_services.py core/sale_price_v60.py core/material_report_v23.py core/material_flow.py core/business_tools_v21.py core/capital_history_v87.py core/inventory_valuation_v17.py Caddyfile || fail "Legacy business or infrastructure source changed"
for file in $(git diff --name-only "$BASE"..HEAD); do
  case "$file" in
    .github/workflows/check-tapsi-shop-v139.yml|core/models.py|core/migrations/0022_tapsi_shop_v138.py|core/tapsi_shop_v138.py|core/tapsi_views_v138.py|core/test_tapsi_shop_v138.py|core/product_center_v93.py|core/daily_report_v8.py|core/daily_views.py|core/daily_report_actions_v21.py|core/urls.py|templates/core/_tapsi_shop_daily_v138.html|templates/core/_tapsi_pricing_v138.html|templates/core/_product_center_pricing_v93.html|templates/core/daily_report_v45.html|templates/core/sale_brand_v45.html|templates/core/daily_report_v21.html|core/static/core/tapsi_shop_v138.js|core/static/core/tapsi_shop_v138.css|server_tapsi_shop_v139.sh) ;;
    *) fail "Out-of-scope file: $file" ;;
  esac
done
[[ -s .env ]] || fail "Missing .env"
docker compose config -q || fail "Docker Compose config invalid"
docker compose ps --status running web | grep -q web || fail "Live web is not running"
docker compose ps --status running db | grep -q db || fail "Database is not running"
CADDY_BEFORE=$(sha256sum Caddyfile | awk '{print $1}')

set -a
. ./.env
set +a
mkdir -p backups
BACKUP="backups/pre-v138-tapsi-shop-$(date +%Y%m%d-%H%M%S).sql"
docker compose exec -T db pg_dump -U "$DB_USER" "$DB_NAME" > "$BACKUP" || fail "PostgreSQL backup failed"
[[ -s "$BACKUP" ]] || fail "Empty backup file"
echo "BACKUP=$BACKUP"

AUDIT='from django.apps import apps
from hashlib import sha256
names = ["StockBalance","InventoryMovement","SaleDay","SaleLine","ProductCode","ProductSize","ProductComposition","RawMaterialStock","MaterialReportBlock","MaterialReportConsumption","MaterialReportOutputApplied","AppSetting","AccountEntry","BusinessPayment"]
for name in names:
 model = apps.get_model("core",name)
 cols = [f.attname for f in model._meta.concrete_fields]
 digest = sha256()
 for row in model.objects.order_by("pk").values_list(*cols).iterator():
  digest.update(repr(row).encode("utf-8"))
  digest.update(b"\\n")
 print(name+"="+digest.hexdigest())'
PATTERN='^(StockBalance|InventoryMovement|SaleDay|SaleLine|ProductCode|ProductSize|ProductComposition|RawMaterialStock|MaterialReportBlock|MaterialReportConsumption|MaterialReportOutputApplied|AppSetting|AccountEntry|BusinessPayment)='
TMP=$(mktemp -d /tmp/tapsi-v138.XXXXXX)
trap 'rm -rf "$TMP"' EXIT
docker compose exec -T web python manage.py shell -c "$AUDIT" | grep -E "$PATTERN" > "$TMP/before" || fail "Pre-deploy business data audit failed"
[[ $(wc -l < "$TMP/before") -eq 14 ]] || fail "Business data audit incomplete"

echo "=== BUILD CANDIDATE WITHOUT RESTARTING LIVE SERVICES ==="
docker compose build web || fail "Candidate build failed: live web untouched"
docker compose run --rm --entrypoint python web manage.py check || fail "Candidate Django check failed"
docker compose run --rm --entrypoint python web manage.py makemigrations --check --dry-run || fail "Model/migration drift"
docker compose run --rm --entrypoint python web manage.py shell -c "from django.db import connection; from django.db.migrations.executor import MigrationExecutor; p=[(m.app_label,m.name,backwards) for m,backwards in MigrationExecutor(connection).migration_plan([('core','0022_tapsi_shop_v138')])]; assert p in ([], [('core','0022_tapsi_shop_v138',False)]), p; print('MIGRATION_PLAN_SAFE',p)" || fail "Unexpected migrations pending"
[[ "$(sha256sum Caddyfile | awk '{print $1}')" == "$CADDY_BEFORE" ]] || fail "Caddyfile unexpectedly changed"

echo "=== ADD ONLY FOUR NEW TAPSI DATABASE TABLES ==="
docker compose run --rm --entrypoint python web manage.py migrate core 0022_tapsi_shop_v138 --noinput || fail "Migration failed; original web stays live, use backup if necessary"
docker compose run --rm --entrypoint python web manage.py shell -c "$AUDIT" | grep -E "$PATTERN" > "$TMP/migrated" || fail "Post-migration business audit failed"
diff -u "$TMP/before" "$TMP/migrated" || fail "Existing business data mutated during migration"

echo "=== SWITCH WEB ONLY ==="
docker compose up -d --no-deps --no-build --force-recreate web || fail "Web recreate failed"
docker compose exec -T web python manage.py check || fail "Live Django check failed"
docker compose exec -T web python manage.py shell -c "from django.urls import reverse; assert reverse('tapsi_order_create',args=[7]) == '/sales/7/tapsi/create/'; print('TAPSI_ROUTE_OK')" || fail "Tapsi route missing"
docker compose exec -T web python manage.py shell -c "$AUDIT" | grep -E "$PATTERN" > "$TMP/after" || fail "Post-deployment audit failed"
diff -u "$TMP/before" "$TMP/after" || fail "Existing financial/stock source data changed during deploy"
[[ "$(sha256sum Caddyfile | awk '{print $1}')" == "$CADDY_BEFORE" ]] || fail "Custom local Caddyfile unexpectedly changed"

docker compose exec -T web python manage.py shell -c "from django.urls import reverse; assert reverse('material_block_inline',args=[7]) == '/material-report/7/inline/'; print('PRODUCTION_INLINE_ROUTE_PRESERVED')" || fail "Existing production inline save missing"
echo "=== RELEASE COMPLETE ==="
echo "V139_TAPSI_SHOP=OK"
echo "EXISTING_BUSINESS_HASHES=UNCHANGED"
echo "DIGIKALA_PRICES=UNCHANGED"
echo "BACKUP=$BACKUP"
docker compose ps
