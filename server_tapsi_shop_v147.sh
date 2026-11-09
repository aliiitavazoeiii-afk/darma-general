#!/usr/bin/env bash
# V147: additive settlement source and new-sheet auto fabric. Preserve all historical records.
# Requires V146 deployed. Full DB backup, additive migration 0025, no existing data rewrite.
set -euo pipefail
cd /opt/darma-general
BASE=a199825d78c509c0233f86ca0ca65ee9fe102236
BRANCH=v147-tapsi-receipts-fabric-auto-transfer
fail(){ echo "STOP: $*" >&2; exit 1; }
echo "=== V147 TAPSI RECEIPTS & NEW SHEET FABRIC AUTO TRANSFER ==="
[[ "$(git branch --show-current)" == "$BRANCH" ]] || fail "Wrong branch"
git merge-base --is-ancestor "$BASE" HEAD || fail "V146 deployed ancestor not preserved"
git diff --quiet -- . ':(exclude)Caddyfile' || fail "Unexpected local tracked source changes"
git diff --cached --quiet -- . ':(exclude)Caddyfile' || fail "Unexpected staged changes"
git diff --quiet "$BASE"..HEAD -- core/finance.py core/final_services.py core/sale_price_v60.py core/pricing_v60.py core/material_flow.py core/inventory_valuation_v17.py Caddyfile || fail "Protected existing business source modified"
for file in $(git diff --name-only "$BASE"..HEAD); do
  case "$file" in
    .github/workflows/check-tapsi-shop-v147.yml|core/models.py|core/models_final.py|core/migrations/0025_tapsi_receipts_auto_fabric_v147.py|core/business_receipts_v64.py|core/tapsi_shop_v138.py|core/finance_overview_v104.py|core/finance_center_v97.py|templates/core/_finance_kpis_v104.html|templates/core/finance_center_v97.html|templates/core/finance_accounts_v97.html|templates/core/payments_v22.html|core/material_report_v23.py|core/material_report_ui_v131.py|core/material_report_v20.py|core/production_fabric_auto_v147.py|core/test_v147_flows.py|core/test_tapsi_shop_v138.py|core/management/commands/check_multi_receipts_v64.py|server_tapsi_shop_v147.sh) ;;
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
BACKUP="backups/pre-v147-receipts-fabric-$(date +%Y%m%d-%H%M%S).sql"
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
TMP=$(mktemp -d /tmp/tapsi-v147.XXXXXX)
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
docker compose run --rm --entrypoint python web manage.py shell -c "from django.urls import reverse; assert reverse('tapsi_home') == '/tapsi-shop/'; assert reverse('tapsi_monthly')=='/tapsi-shop/monthly/'; assert reverse('tapsi_calculator')=='/tapsi-shop/calculator/'; print('V147_TAPSI_ROUTES=READY')" || fail "Tapsi route missing in candidate"
[[ "$(sha256sum Caddyfile | awk '{print $1}')" == "$CADDY_BEFORE" ]] || fail "Caddyfile checksum drift"
echo "=== APPLY ONLY ADDITIVE 0025 (RECEIPT SOURCE AND NEW FABRIC LEDGER) ==="
docker compose run --rm --entrypoint python web manage.py migrate core 0025_tapsi_receipts_auto_fabric_v147 --noinput || fail "V147 migration failed; live web unchanged"
echo "=== SWITCH ONLY WEB CONTAINER ==="
docker compose up -d --no-deps --no-build --force-recreate web || fail "Web restart failed"
docker compose exec -T web python manage.py check || fail "Live Django check failed"
docker compose exec -T web python manage.py shell -c "from django.db.migrations.recorder import MigrationRecorder; from core.models import TapsiOrder; from django.urls import reverse; assert reverse('tapsi_home')=='/tapsi-shop/'; assert reverse('tapsi_calculator')=='/tapsi-shop/calculator/'; assert reverse('tapsi_monthly')=='/tapsi-shop/monthly/'; assert MigrationRecorder.Migration.objects.filter(app='core',name='0025_tapsi_receipts_auto_fabric_v147').exists(); print('V147_ACCOUNTING_AND_ROUTES=OK')" || fail "Live rates or routes invalid"
docker compose exec -T web python manage.py shell -c "$AUDIT" | grep -E "$PATTERN" > "$TMP/after" || fail "Live audit failed"
diff -u "$TMP/before" "$TMP/after" || fail "Protected financial or stock data changed during deployment"
docker compose exec -T web python manage.py shell -c "from core.models import TapsiOrder; print('COUNT='+str(TapsiOrder.objects.count()))" | grep '^COUNT=' > "$TMP/orders-after" || fail "Post-upgrade order count failed"
diff -u "$TMP/orders-before" "$TMP/orders-after" || fail "Tapsi order count changed"
[[ "$(sha256sum Caddyfile | awk '{print $1}')" == "$CADDY_BEFORE" ]] || fail "Caddyfile changed"
echo "V147_TAPSI_RECEIPTS_AND_AUTO_FABRIC=OK"
echo "V147_HISTORICAL_ORDER_AND_STOCK_ROWS=UNCHANGED"
echo "EXISTING_BUSINESS_HASHES=UNCHANGED"
echo "CAPITAL_TAPSI_RECEIVABLE=NET_OF_NEW_SETTLEMENTS"
echo "BACKUP=$BACKUP"
docker compose ps
