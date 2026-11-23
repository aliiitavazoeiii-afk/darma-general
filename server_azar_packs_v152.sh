#!/usr/bin/env bash
# V152: dry-run-first backfill for already booked Darma 06/p12 color allocations from 1 Azar.
# Requires V147 schema deployed. Full DB backup and before/after protected business hashes.
set -euo pipefail
cd /opt/darma-general
BASE=d20ac82f3a215525aa35835df1721520ae5d61d6
BRANCH=v152-azar-06-p12-color-correction
fail(){ echo "STOP: $*" >&2; exit 1; }
echo "=== V152 AZAR 06 / P12 SALE-COLOR CORRECTION ==="
[[ "$(git branch --show-current)" == "$BRANCH" ]] || fail "Wrong branch"
git merge-base --is-ancestor "$BASE" HEAD || fail "V151 code ancestor not preserved"
git diff --quiet -- . ':(exclude)Caddyfile' || fail "Unexpected local tracked source changes"
git diff --cached --quiet -- . ':(exclude)Caddyfile' || fail "Unexpected staged changes"
git diff --quiet "$BASE"..HEAD -- core/models.py core/models_final.py core/migrations core/sale_price_v60.py core/pricing_v60.py core/material_report_v23.py core/material_flow.py core/inventory_valuation_v17.py core/production_fabric_auto_v147.py core/business_receipts_v64.py core/darma_cost_v55.py core/capital_history_v87.py Caddyfile core/daily_order_import_v8.py core/daily_order_import_v23.py core/daily_order_views_v60.py core/material_report_v23.py core/material_report_v20.py core/business_tools_v62.py core/wholesale_logic_v119.py || fail "Protected existing business source modified"
for file in $(git diff --name-only "$BASE"..HEAD); do
  case "$file" in
    .github/workflows/check-azar-packs-v152.yml|core/azar_pack_colors_v152.py|core/final_services.py|core/management/commands/reclassify_azar_packs_v152.py|core/test_azar_pack_colors_v152.py|server_azar_packs_v152.sh) ;;
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
BACKUP="backups/pre-v152-azar-packs-$(date +%Y%m%d-%H%M%S).sql"
docker compose exec -T db pg_dump -U "$DB_USER" "$DB_NAME" > "$BACKUP" || fail "DB backup failed"
[[ -s "$BACKUP" ]] || fail "Empty backup"
echo "BACKUP=$BACKUP"
AUDIT='from django.apps import apps
from hashlib import sha256
names=["StockBalance","InventoryMovement","SaleDay","SaleLine","ProductCode","ProductSize","ProductComposition","RawMaterialStock","MaterialReportBlock","MaterialReportConsumption","MaterialReportOutputApplied","MaterialReportFabricTransfer","AppSetting","AccountEntry","BusinessPayment","DigikalaSettlement","TapsiOrder","TapsiOrderItem","TapsiStockAllocation","Account","ExcelManualRow","MoneyMovement","TapsiPriceRule","WholesaleCustomer","WholesaleInvoice","TailorBalanceEntry","SaleAllocation","SaleShortage"]
for name in names:
 model=apps.get_model("core",name)
 cols=[f.attname for f in model._meta.concrete_fields]
 digest=sha256()
 for row in model.objects.order_by("pk").values_list(*cols).iterator():
  digest.update(repr(row).encode("utf-8"))
  digest.update(b"\\n")
 print(name+"="+digest.hexdigest())'
PATTERN='^(StockBalance|InventoryMovement|SaleDay|SaleLine|ProductCode|ProductSize|ProductComposition|RawMaterialStock|MaterialReportBlock|MaterialReportConsumption|MaterialReportOutputApplied|MaterialReportFabricTransfer|AppSetting|AccountEntry|BusinessPayment|DigikalaSettlement|TapsiOrder|TapsiOrderItem|TapsiStockAllocation|Account|ExcelManualRow|MoneyMovement|TapsiPriceRule|WholesaleCustomer|WholesaleInvoice|TailorBalanceEntry|SaleAllocation|SaleShortage)='
TMP=$(mktemp -d /tmp/darma-v152.XXXXXX)
trap 'rm -rf "$TMP"' EXIT
docker compose exec -T web python manage.py shell -c "$AUDIT" | grep -E "$PATTERN" > "$TMP/before" || fail "Baseline audit failed"
[[ "$(wc -l < "$TMP/before")" -eq 28 ]] || fail "Incomplete audit"
docker compose exec -T web python manage.py shell -c "from core.models import TapsiOrder; print('COUNT='+str(TapsiOrder.objects.count()))" | grep '^COUNT=' > "$TMP/orders-before" || fail "Baseline Tapsi order count failed"
echo "=== BUILD CANDIDATE: DO NOT RESTART LIVE SERVICES ==="
docker compose build web || fail "Candidate build failed (live web unchanged)"
docker compose run --rm --entrypoint python web manage.py check || fail "Candidate Django check failed"
docker compose run --rm --entrypoint python web manage.py makemigrations --check --dry-run || fail "Unexpected migration drift"
docker compose run --rm --entrypoint python web manage.py shell -c "from django.db.migrations.recorder import MigrationRecorder; assert MigrationRecorder.Migration.objects.filter(app='core',name='0025_tapsi_receipts_auto_fabric_v147').exists(), 'V147 schema not deployed'; print('V147_SCHEMA=READY')" || fail "V147 schema missing, deploy V147 first"
docker compose run --rm --entrypoint python web manage.py migrate --plan || fail "Migration plan invalid"
docker compose run --rm --entrypoint python web manage.py reclassify_azar_packs_v152 || fail "V152 historical color preflight failed; live web unchanged"
docker compose run --rm --entrypoint python web manage.py shell -c "from datetime import date; from core.azar_pack_colors_v152 import START_DATE,RULES; assert START_DATE==date(2026,11,22); assert RULES=={'06':(6,'کرم',1),'p12':(12,'طوسی',2)}; print('V152_SCOPED_COMPOSITION_RULES=PASS')" || fail "V152 date/codes guard failed"
[[ "$(sha256sum Caddyfile | awk '{print $1}')" == "$CADDY_BEFORE" ]] || fail "Caddyfile checksum drift"
echo "=== NO DB MIGRATIONS OR DATA BACKFILL ==="
docker compose run --rm --entrypoint python web manage.py migrate --check --noinput || fail "Unexpected pending migrations"
echo "=== SWITCH ONLY WEB CONTAINER ==="
docker compose up -d --no-deps --no-build --force-recreate web || fail "Web restart failed"
docker compose exec -T web python manage.py check || fail "Live Django check failed"
docker compose exec -T web python manage.py reclassify_azar_packs_v152 || fail "V152 live dry-run preflight failed"
docker compose exec -T web python manage.py shell -c "from core.azar_pack_colors_v152 import RULES,START_DATE; assert len(RULES)==2; print('V152_LIVE_DATE_SCOPED_COLOR_ENGINE=OK')" || fail "V152 live code not loaded"
docker compose exec -T web python manage.py shell -c "$AUDIT" | grep -E "$PATTERN" > "$TMP/after" || fail "Live audit failed"
diff -u "$TMP/before" "$TMP/after" || fail "Protected financial or stock data changed during deployment"
docker compose exec -T web python manage.py shell -c "from core.models import TapsiOrder; print('COUNT='+str(TapsiOrder.objects.count()))" | grep '^COUNT=' > "$TMP/orders-after" || fail "Post-upgrade order count failed"
diff -u "$TMP/orders-before" "$TMP/orders-after" || fail "Tapsi order count changed"
[[ "$(sha256sum Caddyfile | awk '{print $1}')" == "$CADDY_BEFORE" ]] || fail "Caddyfile changed"
echo "V152_CODE_AND_DRY_RUN=OK"
echo "V152_BEFORE_APPLY_EXISTING_SALES_AND_STOCK=UNCHANGED"
echo "EXISTING_BUSINESS_HASHES=UNCHANGED"
echo "EXISTING_PRICES_AND_BOOKED_ORDERS_UNCHANGED=YES"
echo "NEXT_STEP: docker compose exec -T web python manage.py reclassify_azar_packs_v152 --apply"
echo "BACKUP=$BACKUP"
docker compose ps
