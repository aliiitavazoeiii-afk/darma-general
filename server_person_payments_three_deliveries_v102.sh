#!/bin/sh
set -eu
cd /opt/darma-general

fail(){ echo ""; echo "======================================"; echo "FAILED: $1"; echo "======================================"; exit 1; }
step(){ echo ""; echo "======================================"; echo "$1"; echo "======================================"; }

[ -f .env ] || fail ".env not found"
set -a
. ./.env || fail "could not load .env"
set +a
export COMPOSE_IGNORE_ORPHANS=1

BASE=0ddd16cecbd4a2ab148c63aee22f556ffa089a58
MIRROR_DOCKERFILE=.Dockerfile.v102.mirror.tmp
MIRROR_COMPOSE=.compose.v102.mirror.tmp.yml
cleanup(){ rm -f "$MIRROR_DOCKERFILE" "$MIRROR_COMPOSE"; }
trap cleanup EXIT INT TERM

build_web(){
  if docker compose build web; then return 0; fi
  echo "Primary build failed. Retrying via mirror.gcr.io ..."
  cleanup
  awk 'NR==1 { if($0!="FROM python:3.12-slim"){exit 42} print "FROM mirror.gcr.io/library/python:3.12-slim"; next } {print}' Dockerfile > "$MIRROR_DOCKERFILE" || return 1
  cat > "$MIRROR_COMPOSE" <<'YAML'
services:
  web:
    build:
      context: .
      dockerfile: .Dockerfile.v102.mirror.tmp
YAML
  docker compose -f compose.yml -f "$MIRROR_COMPOSE" build web || return 1
  cleanup
}

snapshot_code(){
cat <<'PY'
from hashlib import sha256
from core.models import (
    AccountEntry, AppSetting, BusinessPayment, ExcelManualRow, ExcelManualSetting,
    InventoryMovement, MaterialReportBlock, MaterialReportConsumption,
    MaterialReportOutputApplied, RawMaterialStock, SaleLine, SaleSnapshot,
    StockBalance, TailorBalanceEntry,
)
def digest(model):
    fields=[f.attname for f in model._meta.concrete_fields]
    h=sha256()
    for row in model.objects.order_by(model._meta.pk.attname).values_list(*fields):
        h.update(repr(tuple(row)).encode('utf-8')); h.update(b'\n')
    return h.hexdigest()
for label,model in [
    ('MANUAL_ROWS_HASH',ExcelManualRow),('MANUAL_SETTINGS_HASH',ExcelManualSetting),
    ('PAYMENTS_HASH',BusinessPayment),('MATERIAL_BLOCKS_HASH',MaterialReportBlock),
    ('MATERIAL_CONSUMPTION_HASH',MaterialReportConsumption),
    ('MATERIAL_OUTPUT_HASH',MaterialReportOutputApplied),('RAW_HASH',RawMaterialStock),
    ('STOCK_HASH',StockBalance),('MOVEMENT_HASH',InventoryMovement),
    ('TAILOR_HASH',TailorBalanceEntry),('APPSETTINGS_HASH',AppSetting),
    ('SALELINE_HASH',SaleLine),('SNAPSHOT_HASH',SaleSnapshot),('ACCOUNTENTRY_HASH',AccountEntry),
]:
    print('%s=%s' % (label,digest(model)))
PY
}
snapshot_exec(){ CODE=$(snapshot_code); docker compose exec -T web python manage.py shell -c "$CODE" 2>/dev/null | grep -E '^(MANUAL_ROWS_HASH|MANUAL_SETTINGS_HASH|PAYMENTS_HASH|MATERIAL_BLOCKS_HASH|MATERIAL_CONSUMPTION_HASH|MATERIAL_OUTPUT_HASH|RAW_HASH|STOCK_HASH|MOVEMENT_HASH|TAILOR_HASH|APPSETTINGS_HASH|SALELINE_HASH|SNAPSHOT_HASH|ACCOUNTENTRY_HASH)='; }
snapshot_run(){ CODE=$(snapshot_code); docker compose run --rm --entrypoint python web manage.py shell -c "$CODE" 2>/dev/null | grep -E '^(MANUAL_ROWS_HASH|MANUAL_SETTINGS_HASH|PAYMENTS_HASH|MATERIAL_BLOCKS_HASH|MATERIAL_CONSUMPTION_HASH|MATERIAL_OUTPUT_HASH|RAW_HASH|STOCK_HASH|MOVEMENT_HASH|TAILOR_HASH|APPSETTINGS_HASH|SALELINE_HASH|SNAPSHOT_HASH|ACCOUNTENTRY_HASH)='; }

step "1) BACKUP + PRE STATE"
docker compose config -q || fail "compose invalid"
docker compose up -d db || fail "db start failed"
docker compose ps --status running web | grep -q 'web' || fail "live web not running"
mkdir -p backups
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP="backups/before-person-payments-three-deliveries-v102-${STAMP}.sql"
docker compose exec -T db pg_dump -U "$DB_USER" "$DB_NAME" > "$BACKUP" || fail "backup failed"
[ -s "$BACKUP" ] || fail "backup empty"
echo "BACKUP=$BACKUP"
PRE=$(snapshot_exec) || fail "pre snapshot failed"
echo "$PRE"

step "2) VERIFY V102 SOURCE SCOPE"
git cat-file -e "$BASE^{commit}" || fail "V101 base missing"
CHANGED=$(git diff --name-only "$BASE"..HEAD)
echo "$CHANGED"
for f in $CHANGED; do
  case "$f" in
    PROJECT_HANDOFF_CURRENT.md|core/business_tools_v62.py|core/business_tools_v91.py|core/finance_center_v97.py|core/material_report_v23.py|templates/core/material_report_v36.html|core/management/commands/check_person_payments_three_delivery_v102.py|docs/PROJECT_CONTEXT/52_PERSON_PAYMENTS_THREE_DELIVERIES_V102.md|server_person_payments_three_deliveries_v102.sh) ;;
    *) fail "unexpected V102 file changed: $f" ;;
  esac
done

git diff --quiet "$BASE"..HEAD -- \
  core/models.py core/models_final.py core/finance.py core/report_v10.py \
  core/material_flow.py core/material_cost_v23.py core/inventory_v20.py \
  core/inventory_operations_v16.py core/business_receipts_v64.py core/payment_source_v63.py \
  core/sale_price_v60.py core/cost_accounting_v14.py \
  || fail "protected business/model source changed"

step "3) BUILD + REGRESSIONS"
build_web || fail "web build failed"
docker compose run --rm --entrypoint python web manage.py makemigrations --check --dry-run || fail "migration drift"
docker compose run --rm --entrypoint python web manage.py check || fail "Django check failed"
docker compose run --rm --entrypoint python web manage.py check_global_calendar_inventory_v94 || fail "V94 regression failed"
docker compose run --rm --entrypoint python web manage.py check_finance_accounts_submenu_v101 || fail "V101 finance submenu regression failed"
docker compose run --rm --entrypoint python web manage.py check_person_payments_three_delivery_v102 || fail "V102 regression failed"

step "4) PROJECTED STATE"
PROJECTED=$(snapshot_run) || fail "projected snapshot failed"
echo "$PROJECTED"
[ "$PRE" = "$PROJECTED" ] || { echo "--- PRE ---"; echo "$PRE"; echo "--- PROJECTED ---"; echo "$PROJECTED"; fail "V102 image changed business state before live recreate"; }

step "5) RECREATE LIVE WEB"
docker compose up -d --no-deps --force-recreate web || fail "web recreate failed"
sleep 7
docker compose exec -T web python manage.py check || fail "live Django check failed"
docker compose exec -T web python manage.py check_finance_accounts_submenu_v101 || fail "live V101 regression failed"
docker compose exec -T web python manage.py check_person_payments_three_delivery_v102 || fail "live V102 regression failed"

step "6) FINAL STATE"
FINAL=$(snapshot_exec) || fail "final snapshot failed"
echo "$FINAL"
[ "$PRE" = "$FINAL" ] || { echo "--- PRE ---"; echo "$PRE"; echo "--- FINAL ---"; echo "$FINAL"; fail "V102 deployment changed business state"; }

step "7) SUCCESS"
echo "SUCCESS: PERSON PAYMENTS + THREE DELIVERIES V102 DEPLOYED"
echo "Payments: active person accounts are selectable and reduce that person balance atomically"
echo "Payment edit/delete: person balance and selected bank source reverse/reapply atomically"
echo "Material report: each delivered size cell has three internal receipt boxes"
echo "Material report sync: inventory/wage use the SUM of the three boxes"
echo "Historical single delivery values: shown in box 1 with boxes 2/3 empty"
echo "No migration and no automatic historical rewrite"
echo "Backup: $BACKUP"
