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

BASE=fae04cecc2d34a3c92c8a39052f62c36699cce0b
MIRROR_DOCKERFILE=.Dockerfile.v101.mirror.tmp
MIRROR_COMPOSE=.compose.v101.mirror.tmp.yml
cleanup(){ rm -f "$MIRROR_DOCKERFILE" "$MIRROR_COMPOSE"; }
trap cleanup EXIT INT TERM

build_web(){
  if docker compose build web; then return 0; fi
  echo "Primary build failed. Retrying via mirror.gcr.io ..."
  awk 'NR==1 { if($0!="FROM python:3.12-slim"){exit 42} print "FROM mirror.gcr.io/library/python:3.12-slim"; next } {print}' Dockerfile > "$MIRROR_DOCKERFILE" || return 1
  cat > "$MIRROR_COMPOSE" <<'YAML'
services:
  web:
    build:
      context: .
      dockerfile: .Dockerfile.v101.mirror.tmp
YAML
  docker compose -f compose.yml -f "$MIRROR_COMPOSE" build web
}

snapshot_code(){
cat <<'PY'
from hashlib import sha256
from core.models import (
    AccountEntry, BusinessPayment, DigikalaSettlement, ExcelManualRow,
    ExcelManualSetting, InventoryMovement, RawMaterialStock, SaleLine,
    SaleSnapshot, StockBalance,
)
def digest(model):
    fields=[f.attname for f in model._meta.concrete_fields]
    h=sha256()
    for row in model.objects.order_by(model._meta.pk.attname).values_list(*fields):
        h.update(repr(tuple(row)).encode('utf-8')); h.update(b'\n')
    return h.hexdigest()
for label,model in [
    ('RAW_HASH',RawMaterialStock),('STOCK_HASH',StockBalance),('MOVEMENT_HASH',InventoryMovement),
    ('SALELINE_HASH',SaleLine),('SNAPSHOT_HASH',SaleSnapshot),('ACCOUNTENTRY_HASH',AccountEntry),
    ('MANUAL_SETTINGS_HASH',ExcelManualSetting),('MANUAL_ROWS_HASH',ExcelManualRow),
    ('PAYMENTS_HASH',BusinessPayment),('RECEIPTS_HASH',DigikalaSettlement),
]:
    print('%s=%s' % (label,digest(model)))
PY
}
snapshot_exec(){ CODE=$(snapshot_code); docker compose exec -T web python manage.py shell -c "$CODE" 2>/dev/null | grep -E '^(RAW_HASH|STOCK_HASH|MOVEMENT_HASH|SALELINE_HASH|SNAPSHOT_HASH|ACCOUNTENTRY_HASH|MANUAL_SETTINGS_HASH|MANUAL_ROWS_HASH|PAYMENTS_HASH|RECEIPTS_HASH)='; }
snapshot_run(){ CODE=$(snapshot_code); docker compose run --rm --entrypoint python web manage.py shell -c "$CODE" 2>/dev/null | grep -E '^(RAW_HASH|STOCK_HASH|MOVEMENT_HASH|SALELINE_HASH|SNAPSHOT_HASH|ACCOUNTENTRY_HASH|MANUAL_SETTINGS_HASH|MANUAL_ROWS_HASH|PAYMENTS_HASH|RECEIPTS_HASH)='; }

step "1) BACKUP + PRE STATE"
docker compose config -q || fail "compose invalid"
docker compose up -d db || fail "db start failed"
docker compose ps --status running web | grep -q 'web' || fail "live web not running"
mkdir -p backups
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP="backups/before-finance-accounts-submenu-v101-${STAMP}.sql"
docker compose exec -T db pg_dump -U "$DB_USER" "$DB_NAME" > "$BACKUP" || fail "backup failed"
[ -s "$BACKUP" ] || fail "backup empty"
echo "BACKUP=$BACKUP"
PRE=$(snapshot_exec) || fail "pre snapshot failed"
echo "$PRE"

step "2) VERIFY V101 SCOPE"
git cat-file -e "$BASE^{commit}" || fail "V99 base missing"
CHANGED=$(git diff --name-only "$BASE"..HEAD)
echo "$CHANGED"
for f in $CHANGED; do
  case "$f" in
    static/core/number_format.js|core/ui_polish_v98.py|core/management/commands/check_finance_accounts_submenu_v101.py|server_finance_accounts_submenu_v101.sh) ;;
    *) fail "unexpected V101 file changed: $f" ;;
  esac
done

git diff --quiet "$BASE"..HEAD -- core/models.py core/finance.py core/report_v10.py core/finance_center_v97.py core/business_tools_v91.py core/business_tools_v62.py core/business_receipts_v64.py core/calculator_v37.py core/material_flow.py core/inventory_v20.py || fail "protected business source changed"

step "3) BUILD + REGRESSIONS"
build_web || fail "web build failed"
docker compose run --rm --entrypoint python web manage.py makemigrations --check --dry-run || fail "migration drift"
docker compose run --rm --entrypoint python web manage.py check || fail "Django check failed"
docker compose run --rm --entrypoint python web manage.py check_global_calendar_inventory_v94 || fail "V94 regression failed"
docker compose run --rm --entrypoint python web manage.py check_finance_accounts_submenu_v101 || fail "V101 accounts regression failed"

step "4) PROJECTED STATE"
PROJECTED=$(snapshot_run) || fail "projected snapshot failed"
echo "$PROJECTED"
[ "$PRE" = "$PROJECTED" ] || { echo "--- PRE ---"; echo "$PRE"; echo "--- PROJECTED ---"; echo "$PROJECTED"; fail "V101 image changed business state"; }

step "5) RECREATE LIVE WEB"
docker compose up -d --no-deps --force-recreate web || fail "web recreate failed"
sleep 7
docker compose exec -T web python manage.py check || fail "live Django check failed"
docker compose exec -T web python manage.py check_finance_accounts_submenu_v101 || fail "live V101 regression failed"

step "6) FINAL STATE"
FINAL=$(snapshot_exec) || fail "final snapshot failed"
echo "$FINAL"
[ "$PRE" = "$FINAL" ] || { echo "--- PRE ---"; echo "$PRE"; echo "--- FINAL ---"; echo "$FINAL"; fail "V101 deployment changed business state"; }

step "7) SUCCESS"
echo "SUCCESS: FINANCE ACCOUNTS SUBMENU V101 DEPLOYED"
echo "Finance & Tools submenu: Payments + Accounts + Calculator"
echo "Accounts page: same ACCOUNTS/PERSONS source previously used by comprehensive report"
echo "No finance/inventory/accounting formulas changed"
echo "Backup: $BACKUP"
