#!/bin/sh
set -eu

MAIN_DIR=/opt/darma-general
EXPENSE_DIR=/opt/darma-expense
BASE=40ba4293dcd7b05fedef33f37f70ebcbeedd8655
EXPENSE_PORT="${EXPENSE_PORT:-8011}"

fail(){ echo ""; echo "======================================"; echo "FAILED: $1"; echo "======================================"; exit 1; }
step(){ echo ""; echo "======================================"; echo "$1"; echo "======================================"; }

[ -d "$MAIN_DIR" ] || fail "main project directory not found: $MAIN_DIR"
[ -f "$MAIN_DIR/.env" ] || fail "main .env not found"
[ -d "$EXPENSE_DIR" ] || fail "expense worktree not found: $EXPENSE_DIR"

set -a
. "$MAIN_DIR/.env" || fail "could not load main .env"
set +a

cd "$MAIN_DIR"
docker compose config -q || fail "main compose invalid"
docker compose up -d db web || fail "main db/web start failed"

DB_CONTAINER=$(docker compose ps -q db)
[ -n "$DB_CONTAINER" ] || fail "main PostgreSQL container was not found"
DARMA_NETWORK=$(docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}}{{"\n"}}{{end}}' "$DB_CONTAINER" | sed '/^$/d' | head -n1)
[ -n "$DARMA_NETWORK" ] || fail "could not discover main Docker network"
export DARMA_NETWORK
export EXPENSE_PORT

cd "$EXPENSE_DIR"

expense_dc() {
  docker compose -p darma-expense -f compose.expense.yml "$@"
}

snapshot_main() {
  cd "$MAIN_DIR"
  docker compose exec -T web python manage.py shell -c '
from django.db.models import Sum
from core.dia_gallery_v45 import dia_gallery_receivable_total
from core.finance_excel_v9 import digikala_receivable_total
from core.inventory_valuation_v17 import finished_inventory_value_v17
from core.models import Brand,BusinessPayment,DigikalaSettlement,ExcelManualRow,ExcelManualSetting,InventoryMovement,RawMaterialStock,SaleLine,StockBalance,TakvinPurchase
from core.report_v5 import _raw_material_context

def norm(s):
    return str(s or "").replace(" ","").replace("ي","ی").replace("ك","ک")
def row_balance(needle):
    for r in ExcelManualRow.objects.filter(active=True,section=ExcelManualRow.ACCOUNTS).order_by("sort_order","id"):
        if needle in norm(r.title): return int(r.amount or 0)
    return 0
def bqty(name):
    b=Brand.objects.get(name=name)
    return int(StockBalance.objects.filter(brand=b).aggregate(v=Sum("qty"))["v"] or 0)

rows=ExcelManualRow.objects.filter(active=True)
accounts=sum(int(x.amount or 0) for x in rows.filter(section=ExcelManualRow.ACCOUNTS).exclude(note__startswith="[system:self-spend-v62]"))
persons=sum(int(x.amount or 0) for x in rows.filter(section=ExcelManualRow.PERSONS))
dia=int(dia_gallery_receivable_total())
assets=sum(int(x.amount or 0) for x in rows.filter(section=ExcelManualRow.ASSETS))
finished=int(finished_inventory_value_v17())
raw=int(_raw_material_context()["materials_total"])
digi=int(digikala_receivable_total())
debt=int(ExcelManualSetting.objects.filter(key="takvin_debt").values_list("value",flat=True).first() or 0)
capital=accounts+persons+dia+assets+finished+raw+digi-debt
print("CAPITAL=%d" % capital)
print("MELLAT=%d" % row_balance("ملت"))
print("MOFID=%d" % row_balance("مفید"))
print("FINISHED=%d" % finished)
print("RAW=%d" % raw)
print("DIGI=%d" % digi)
print("DIA=%d" % dia)
print("TAKVIN_DEBT=%d" % debt)
print("DARMA_QTY=%d" % bqty("دارما"))
print("TAKVIN_QTY=%d" % bqty("تکوین"))
print("NOVANI_QTY=%d" % bqty("Novani"))
print("SALES=%d" % SaleLine.objects.count())
print("PAYMENTS=%d" % BusinessPayment.objects.count())
print("RECEIPTS=%d" % DigikalaSettlement.objects.count())
print("RAW_ROWS=%d" % RawMaterialStock.objects.count())
print("MOVEMENTS=%d" % InventoryMovement.objects.count())
print("TAKVIN_PURCHASES=%d" % TakvinPurchase.objects.count())
' 2>/dev/null | grep -E '^(CAPITAL|MELLAT|MOFID|FINISHED|RAW|DIGI|DIA|TAKVIN_DEBT|DARMA_QTY|TAKVIN_QTY|NOVANI_QTY|SALES|PAYMENTS|RECEIPTS|RAW_ROWS|MOVEMENTS|TAKVIN_PURCHASES)='
  cd "$EXPENSE_DIR"
}

step "1) MAIN DATABASE BACKUP + PROTECTED PRE STATE"
cd "$MAIN_DIR"
i=1
while [ "$i" -le 30 ]; do
  docker compose exec -T db pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1 && break
  [ "$i" -eq 30 ] && fail "PostgreSQL not ready"
  sleep 1
  i=$((i+1))
done
mkdir -p backups
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP="$MAIN_DIR/backups/before-expense-tracker-v1-${STAMP}.sql"
docker compose exec -T db pg_dump -U "$DB_USER" "$DB_NAME" > "$BACKUP" || fail "database backup failed"
[ -s "$BACKUP" ] || fail "database backup is empty"
cd "$EXPENSE_DIR"
PRE=$(snapshot_main) || fail "could not capture protected pre state"
echo "$PRE"
echo "BACKUP=$BACKUP"
echo "MAIN_NETWORK=$DARMA_NETWORK"

step "2) VERIFY EXPENSE BRANCH ISOLATION"
git cat-file -e "$BASE^{commit}" || fail "expense base commit missing"
CHANGED=$(git diff --name-only "$BASE"..HEAD)
echo "$CHANGED"
for f in $CHANGED; do
  case "$f" in
    expense_site/*|expense_tracker/*|templates/expense_tracker/*|static/expense_tracker/*|Dockerfile.expense|compose.expense.yml|expense_entrypoint.sh|server_expense_tracker_v1.sh|docs/EXPENSE_TRACKER_V1.md) ;;
    *) fail "unexpected file changed on isolated expense branch: $f" ;;
  esac
done

git diff --quiet "$BASE"..HEAD -- core config compose.yml compose.telegram.yml Caddyfile entrypoint.sh templates/core static/core   || fail "existing ERP source changed on expense branch"

[ ! -f .env ] || fail "expense worktree must not contain .env"
[ ! -d backups ] || fail "expense worktree must not contain database backups"

step "3) BUILD ISOLATED EXPENSE SERVICE"
expense_dc config -q || fail "expense compose invalid"
expense_dc build expense-web || fail "expense web build failed"
expense_dc run --rm --entrypoint python expense-web manage.py makemigrations --check --dry-run --settings=expense_site.settings || fail "expense migration drift"
expense_dc run --rm --entrypoint python expense-web manage.py check --settings=expense_site.settings || fail "expense Django check failed"

step "4) APPLY ONLY EXPENSE MIGRATIONS"
expense_dc run --rm --entrypoint python expense-web manage.py migrate expense_tracker --settings=expense_site.settings --noinput || fail "expense migration failed"
POST_MIGRATE=$(snapshot_main) || fail "could not capture post-migration main state"
[ "$PRE" = "$POST_MIGRATE" ] || {
  echo "--- PRE ---"; echo "$PRE"
  echo "--- POST MIGRATE ---"; echo "$POST_MIGRATE"
  fail "expense schema migration changed protected ERP business state"
}

step "5) ROLLBACK-ONLY EXPENSE REGRESSION"
expense_dc run --rm --entrypoint python expense-web manage.py check_expense_tracker_v1 --settings=expense_site.settings || fail "expense regression failed"
POST_TEST=$(snapshot_main) || fail "could not capture post-test main state"
[ "$PRE" = "$POST_TEST" ] || {
  echo "--- PRE ---"; echo "$PRE"
  echo "--- POST TEST ---"; echo "$POST_TEST"
  fail "expense regression leaked into ERP business state"
}

step "6) START DEDICATED EXPENSE CONTAINER"
expense_dc up -d --force-recreate expense-web || fail "expense container start failed"
sleep 6
expense_dc exec -T expense-web python manage.py check --settings=expense_site.settings || fail "live expense Django check failed"
expense_dc exec -T expense-web python manage.py check_expense_tracker_v1 --settings=expense_site.settings || fail "live expense regression failed"

step "7) FINAL ERP INVARIANTS"
FINAL=$(snapshot_main) || fail "could not capture final main state"
echo "$FINAL"
[ "$PRE" = "$FINAL" ] || {
  echo "--- PRE ---"; echo "$PRE"
  echo "--- FINAL ---"; echo "$FINAL"
  fail "expense deployment changed protected ERP business state"
}

step "8) SUCCESS"
echo "SUCCESS: EXPENSE TRACKER UI V2 DEPLOYED"
echo "Expense service: darma-expense / expense-web"
echo "Expense port: $EXPENSE_PORT"
echo "ERP web container: NOT RECREATED"
echo "ERP Caddy configuration: NOT CHANGED"
echo "Only shared business bridge: canonical Mellat balance"
echo "Secrets copied into expense image: NO"
echo "Backup: $BACKUP"
