#!/usr/bin/env bash
# V150: one-off Tapsi order prices and a read-only complete tailor ledger with XLSX.
# Requires V147 schema deployed. Full DB backup and before/after protected business hashes.
set -euo pipefail
cd /opt/darma-general
BASE=d1fd87ff3a0b6e94b24de72d4c6fd4572a352a5b
BRANCH=v150-tapsi-order-price-tailor-ledger
fail(){ echo "STOP: $*" >&2; exit 1; }
echo "=== V150 TAPSI PRICE & TAILOR LEDGER ==="
[[ "$(git branch --show-current)" == "$BRANCH" ]] || fail "Wrong branch"
git merge-base --is-ancestor "$BASE" HEAD || fail "V149 code ancestor not preserved"
git diff --quiet -- . ':(exclude)Caddyfile' || fail "Unexpected local tracked source changes"
git diff --cached --quiet -- . ':(exclude)Caddyfile' || fail "Unexpected staged changes"
git diff --quiet "$BASE"..HEAD -- core/models.py core/models_final.py core/migrations core/finance.py core/final_services.py core/sale_price_v60.py core/pricing_v60.py core/material_report_v23.py core/material_flow.py core/inventory_valuation_v17.py core/production_fabric_auto_v147.py core/tapsi_shop_v138.py core/business_receipts_v64.py core/darma_cost_v55.py core/capital_history_v87.py Caddyfile core/daily_order_import_v8.py core/daily_order_import_v12.py core/daily_order_import_v23.py core/daily_order_views_v60.py core/material_report_v23.py core/material_report_v20.py core/business_tools_v62.py core/wholesale_logic_v119.py || fail "Protected existing business source modified"
for file in $(git diff --name-only "$BASE"..HEAD); do
  case "$file" in
    .github/workflows/check-tapsi-price-tailor-v150.yml|core/tapsi_shop_v138.py|core/tapsi_portal_v142.py|core/static/core/tapsi_portal_v142.js|core/static/core/tapsi_portal_v142.css|templates/core/tapsi_shop_v142.html|core/tailor_ledger_v150.py|templates/core/tailor_ledger_v150.html|core/material_report_ui_v131.py|templates/core/material_report_v131.html|core/static/core/production_workspace_v131.css|core/urls.py|core/test_v150_tapsi_tailor.py|server_tapsi_price_tailor_v150.sh) ;;
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
BACKUP="backups/pre-v150-tapsi-tailor-$(date +%Y%m%d-%H%M%S).sql"
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
TMP=$(mktemp -d /tmp/darma-v150.XXXXXX)
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
docker compose run --rm --entrypoint python web manage.py shell -c "from django.urls import reverse; from django.utils import timezone; from core.tailor_ledger_v150 import build_tailor_ledger,live_tailor_balance; from core.tapsi_shop_v138 import current_catalog; assert reverse('tailor_ledger')=='/material-report/tailor-ledger/'; assert reverse('tailor_ledger_xlsx')=='/material-report/tailor-ledger/export.xlsx'; d=build_tailor_ledger(); assert d['current']==live_tailor_balance(); assert d['entries'][-1]['balance']==d['current'] if d['entries'] else d['base_reconstructed']==d['current']; current_catalog(timezone.localdate()); print('V150_CANDIDATE_LEDGER_AND_CATALOG=PASS')" || fail "Candidate ledger/catalog preflight failed"
[[ "$(sha256sum Caddyfile | awk '{print $1}')" == "$CADDY_BEFORE" ]] || fail "Caddyfile checksum drift"
echo "=== NO DB MIGRATIONS OR DATA BACKFILL ==="
docker compose run --rm --entrypoint python web manage.py migrate --check --noinput || fail "Unexpected pending migrations"
echo "=== SWITCH ONLY WEB CONTAINER ==="
docker compose up -d --no-deps --no-build --force-recreate web || fail "Web restart failed"
docker compose exec -T web python manage.py check || fail "Live Django check failed"
docker compose exec -T web python manage.py shell -c "from django.urls import reverse; from core.tailor_ledger_v150 import build_tailor_ledger,live_tailor_balance; d=build_tailor_ledger(); assert d['current']==live_tailor_balance(); assert reverse('tailor_ledger')=='/material-report/tailor-ledger/'; print('V150_TAILOR_LEDGER_LIVE=OK')" || fail "Live tailor ledger preflight failed"
docker compose exec -T web python manage.py shell -c "$AUDIT" | grep -E "$PATTERN" > "$TMP/after" || fail "Live audit failed"
diff -u "$TMP/before" "$TMP/after" || fail "Protected financial or stock data changed during deployment"
docker compose exec -T web python manage.py shell -c "from core.models import TapsiOrder; print('COUNT='+str(TapsiOrder.objects.count()))" | grep '^COUNT=' > "$TMP/orders-after" || fail "Post-upgrade order count failed"
diff -u "$TMP/orders-before" "$TMP/orders-after" || fail "Tapsi order count changed"
[[ "$(sha256sum Caddyfile | awk '{print $1}')" == "$CADDY_BEFORE" ]] || fail "Caddyfile changed"
echo "V150_TAPSI_PRICE_TAILOR_LEDGER=OK"
echo "V150_EXISTING_SALES_TAILOR_STOCK=UNCHANGED"
echo "EXISTING_BUSINESS_HASHES=UNCHANGED"
echo "EXISTING_PRICES_AND_BOOKED_ORDERS_UNCHANGED=YES"
echo "BACKUP=$BACKUP"
docker compose ps
