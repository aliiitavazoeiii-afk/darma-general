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

BASE=d757711676ae811258ec8a8852b991ce7ffa370d

snapshot_code(){
cat <<'PY'
from hashlib import sha256
from core.models import (
    BusinessPayment, ExcelManualRow, InventoryMovement, MaterialReportBlock,
    MaterialReportConsumption, MaterialReportOutputApplied, RawMaterialStock,
    SaleLine, SaleSnapshot, StockBalance,
)
def digest(model):
    fields=[f.attname for f in model._meta.concrete_fields]
    h=sha256()
    for row in model.objects.order_by(model._meta.pk.attname).values_list(*fields):
        h.update(repr(tuple(row)).encode("utf-8")); h.update(b"\n")
    return h.hexdigest()
for label,model in [
    ("RAW_HASH",RawMaterialStock),
    ("MATERIAL_CONSUMPTION_HASH",MaterialReportConsumption),
    ("MATERIAL_OUTPUT_HASH",MaterialReportOutputApplied),
    ("MATERIAL_BLOCK_HASH",MaterialReportBlock),
    ("STOCK_HASH",StockBalance),
    ("MOVEMENT_HASH",InventoryMovement),
    ("SALELINE_HASH",SaleLine),
    ("SNAPSHOT_HASH",SaleSnapshot),
    ("MANUAL_ROWS_HASH",ExcelManualRow),
    ("PAYMENTS_HASH",BusinessPayment),
]:
    print("%s=%s" % (label,digest(model)))
PY
}
snapshot_exec(){ CODE=$(snapshot_code); docker compose exec -T web python manage.py shell -c "$CODE" 2>/dev/null | grep -E '^(RAW_HASH|MATERIAL_CONSUMPTION_HASH|MATERIAL_OUTPUT_HASH|MATERIAL_BLOCK_HASH|STOCK_HASH|MOVEMENT_HASH|SALELINE_HASH|SNAPSHOT_HASH|MANUAL_ROWS_HASH|PAYMENTS_HASH)='; }
snapshot_run(){ CODE=$(snapshot_code); docker compose run --rm --entrypoint python web manage.py shell -c "$CODE" 2>/dev/null | grep -E '^(RAW_HASH|MATERIAL_CONSUMPTION_HASH|MATERIAL_OUTPUT_HASH|MATERIAL_BLOCK_HASH|STOCK_HASH|MOVEMENT_HASH|SALELINE_HASH|SNAPSHOT_HASH|MANUAL_ROWS_HASH|PAYMENTS_HASH)='; }

step "1) BACKUP + PRE STATE"
docker compose config -q || fail "compose invalid"
docker compose up -d db || fail "db start failed"
docker compose ps --status running web | grep -q 'web' || fail "live web not running"
mkdir -p backups
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP="backups/before-direct-finance-nav-v103-${STAMP}.sql"
docker compose exec -T db pg_dump -U "$DB_USER" "$DB_NAME" > "$BACKUP" || fail "backup failed"
[ -s "$BACKUP" ] || fail "backup empty"
PRE=$(snapshot_exec) || fail "pre snapshot failed"
echo "$PRE"

step "2) VERIFY V103 SCOPE"
CHANGED=$(git diff --name-only "$BASE"..HEAD)
echo "$CHANGED"
for f in $CHANGED; do
  case "$f" in
    templates/base.html|core/ui_polish_v98.py|core/management/commands/check_direct_finance_nav_v103.py|server_direct_finance_nav_v103.sh) ;;
    *) fail "unexpected V103 file changed: $f" ;;
  esac
done

git diff --quiet "$BASE"..HEAD --   core/models.py core/models_final.py core/finance.py core/business_tools_v62.py   core/business_tools_v91.py core/finance_center_v97.py core/material_report_v23.py   core/material_report_v92.py core/material_flow.py   || fail "V102 business/material source unexpectedly changed"

step "3) BUILD + REGRESSIONS"
docker compose build web || fail "web build failed"
docker compose run --rm --entrypoint python web manage.py makemigrations --check --dry-run || fail "migration drift"
docker compose run --rm --entrypoint python web manage.py check || fail "Django check failed"
docker compose run --rm --entrypoint python web manage.py check_direct_finance_nav_v103 || fail "V103 finance route/template regression failed"
docker compose run --rm --entrypoint python web manage.py check_material_month_archive_v92 || fail "V92 material regression failed"
docker compose run --rm --entrypoint python web manage.py check_person_payment_split_delivery_v102 || fail "V102 regression failed"

step "4) PROJECTED STATE"
PROJECTED=$(snapshot_run) || fail "projected snapshot failed"
echo "$PROJECTED"
[ "$PRE" = "$PROJECTED" ] || fail "V103 image changed business state"

step "5) RECREATE LIVE WEB"
docker compose up -d --no-deps --force-recreate web || fail "web recreate failed"
sleep 7
docker compose exec -T web python manage.py check || fail "live Django check failed"
docker compose exec -T web python manage.py check_person_payment_split_delivery_v102 || fail "live V102 regression failed"
docker compose exec -T web python manage.py check_direct_finance_nav_v103 || fail "live V103 regression failed"

step "6) FINAL STATE"
FINAL=$(snapshot_exec) || fail "final snapshot failed"
echo "$FINAL"
[ "$PRE" = "$FINAL" ] || fail "V103 deployment changed business state"

step "7) SUCCESS"
echo "SUCCESS: DIRECT FINANCE NAV V103 DEPLOYED"
echo "Finance & Tools: one direct /finance/ sidebar entry"
echo "Finance hub: Payments/Receipts + Accounts + Calculator"
echo "V102 person payments/material split/color progress: preserved"
echo "Backup: $BACKUP"
