#!/usr/bin/env bash
# V140: preserve existing Digikala, production, bank and Caddy records.
# Installation from installed V139 (including already-applied core.0022 migration).
set -euo pipefail
cd /opt/darma-general
BASE=4c42cdc805ce4ac9297e43063164ad5d3d96c8ca
BRANCH=v140-tapsi-workflow-prices-capital
fail(){ echo "STOP: $*" >&2; exit 1; }
echo "=== V140 TAPSI WORKFLOW AND CAPITAL INTEGRATION ==="
[[ "$(git branch --show-current)" == "$BRANCH" ]] || fail "Wrong branch"
git merge-base --is-ancestor "$BASE" HEAD || fail "Installed V139 baseline not preserved"
git diff --quiet -- . ':(exclude)Caddyfile' || fail "Unexpected local tracked source changes"
git diff --cached --quiet -- . ':(exclude)Caddyfile' || fail "Unexpected staged changes"
git diff --quiet "$BASE"..HEAD -- core/finance.py core/final_services.py core/sale_price_v60.py core/pricing_v60.py core/daily_report_actions_v21.py core/models.py core/material_report_v23.py core/material_flow.py core/inventory_valuation_v17.py Caddyfile || fail "Protected existing business source modified"
for file in $(git diff --name-only "$BASE"..HEAD); do
  case "$file" in
    .github/workflows/check-tapsi-shop-v140.yml|core/tapsi_shop_v138.py|core/tapsi_views_v138.py|core/test_tapsi_shop_v138.py|core/report_v10.py|core/capital_history_v87.py|core/excel_dashboard_v89.py|core/finance_center_v97.py|core/management/commands/seed_tapsi_prices_v140.py|core/urls.py|templates/core/daily_report_v45.html|templates/core/daily_report_v21.html|templates/core/sale_brand_v45.html|templates/core/finance_accounts_v97.html|templates/core/report_excel.html|templates/core/report_excel_v97.html|templates/core/_tapsi_order_entry_v140.html|templates/core/_tapsi_report_daily_v140.html|templates/core/_tapsi_comprehensive_v140.html|templates/core/tapsi_order_entry_v140.html|templates/core/tapsi_order_report_v140.html|server_tapsi_shop_v140.sh) ;;
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
BACKUP="backups/pre-v140-tapsi-price-capital-$(date +%Y%m%d-%H%M%S).sql"
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
TMP=$(mktemp -d /tmp/tapsi-v140.XXXXXX)
trap 'rm -rf "$TMP"' EXIT
docker compose exec -T web python manage.py shell -c "$AUDIT" | grep -E "$PATTERN" > "$TMP/before" || fail "Baseline audit failed"
[[ "$(wc -l < "$TMP/before")" -eq 17 ]] || fail "Incomplete audit"
echo "=== BUILD CANDIDATE: DO NOT RESTART LIVE SERVICES ==="
docker compose build web || fail "Candidate build failed (live web unchanged)"
docker compose run --rm --entrypoint python web manage.py check || fail "Candidate Django check failed"
docker compose run --rm --entrypoint python web manage.py makemigrations --check --dry-run || fail "Unexpected migration drift"
docker compose run --rm --entrypoint python web manage.py shell -c "from django.db.migrations.recorder import MigrationRecorder; assert ('core','0022_tapsi_shop_v138') in MigrationRecorder.Migration.objects.values_list('app','name'), 'V139 Tapsi tables not installed'; print('TAPSI_SCHEMA=READY')" || fail "Required existing Tapsi schema missing"
docker compose run --rm --entrypoint python web manage.py seed_tapsi_prices_v140 --dry-run || fail "Tapsi price snapshot preflight failed"
[[ "$(sha256sum Caddyfile | awk '{print $1}')" == "$CADDY_BEFORE" ]] || fail "Caddyfile checksum drift"
echo "=== COPY ONLY MISSING TAPSI PRICES FROM TODAY'S DIGIKALA ==="
docker compose run --rm --entrypoint python web manage.py seed_tapsi_prices_v140 || fail "Tapsi price seeding failed; live web still active"
docker compose run --rm --entrypoint python web manage.py shell -c "$AUDIT" | grep -E "$PATTERN" > "$TMP/seeded" || fail "Post-seeding audit failed"
diff -u "$TMP/before" "$TMP/seeded" || fail "Existing business tables modified during Tapsi price seed"
echo "=== SWITCH ONLY WEB CONTAINER ==="
docker compose up -d --no-deps --no-build --force-recreate web || fail "Web restart failed"
docker compose exec -T web python manage.py check || fail "Live Django check failed"
docker compose exec -T web python manage.py shell -c "from django.urls import reverse; assert reverse('tapsi_order_entry',args=[7]) == '/sales/7/tapsi/'; assert reverse('material_block_inline',args=[7]) == '/material-report/7/inline/'; print('TAPSI_ENTRY_AND_PRODUCTION_ROUTES=OK')" || fail "Required routes missing"
docker compose exec -T web python manage.py shell -c "$AUDIT" | grep -E "$PATTERN" > "$TMP/after" || fail "Live audit failed"
diff -u "$TMP/before" "$TMP/after" || fail "Protected financial or stock data changed during deployment"
[[ "$(sha256sum Caddyfile | awk '{print $1}')" == "$CADDY_BEFORE" ]] || fail "Caddyfile changed"
echo "V140_TAPSI_WORKFLOW=OK"
echo "V140_PRICE_SEED=OK"
echo "EXISTING_BUSINESS_HASHES=UNCHANGED"
echo "CAPITAL_TAPSI_RECEIVABLE=INCLUDED"
echo "BACKUP=$BACKUP"
docker compose ps
