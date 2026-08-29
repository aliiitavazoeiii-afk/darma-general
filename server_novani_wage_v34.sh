#!/bin/sh
set -eu
cd /opt/darma-general

fail(){ echo ""; echo "======================================"; echo "FAILED: $1"; echo "======================================"; exit 1; }
step(){ echo ""; echo "======================================"; echo "$1"; echo "======================================"; }

[ -f .env ] || fail ".env not found"
set -a
. ./.env || fail "could not load .env"
set +a

step "1) START DATABASE"
docker compose up -d db || fail "database start failed"
i=1
while [ "$i" -le 30 ]; do
  docker compose exec -T db pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1 && break
  [ "$i" -eq 30 ] && fail "PostgreSQL did not become ready"
  sleep 1
  i=$((i+1))
done

step "2) FULL DATABASE BACKUP"
mkdir -p backups
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP="backups/before-novani-wage-v34-${STAMP}.sql"
docker compose exec -T db pg_dump -U "$DB_USER" "$DB_NAME" > "$BACKUP" || fail "database backup failed"
[ -s "$BACKUP" ] || fail "database backup is empty"
echo "BACKUP = $BACKUP"

step "3) BUILD LATEST WEB IMAGE"
docker compose build web || fail "web build failed"

step "4) PREFLIGHT"
docker compose run --rm --entrypoint python web manage.py check || fail "Django check failed"
docker compose run --rm --entrypoint python web manage.py makemigrations --check --dry-run || fail "migration drift detected"
docker compose run --rm --entrypoint python web manage.py check_novani_wage_v34 || fail "Novani wage regression check failed"

step "5) DRY-RUN CURRENT MISSING WAGE REPAIR"
DRY=$(docker compose run --rm --entrypoint python web manage.py repair_novani_wage_v34 \
  --expected-pieces 3160 \
  --expected-wage 26333333) || fail "repair dry-run failed; nothing was changed"
echo "$DRY"
printf '%s\n' "$DRY" | grep -q '^NOVANI_V21_PIECES=3160$' || fail "latest Novani v21 output is not 3160 pieces"
printf '%s\n' "$DRY" | grep -q '^DOZEN_WAGE=100000$' || fail "configured dozen wage is not 100,000"
printf '%s\n' "$DRY" | grep -q '^MISSING_WAGE=26333333$' || fail "calculated missing wage is not 26,333,333"
printf '%s\n' "$DRY" | grep -q '^REPAIR_ALREADY_APPLIED=0$' || fail "this block appears already repaired"
BLOCK_ID=$(printf '%s\n' "$DRY" | awk -F= '/^BLOCK_ID=/{print $2}')
[ -n "$BLOCK_ID" ] || fail "could not determine Novani block id"
echo "TARGET BLOCK = $BLOCK_ID"

step "6) CAPTURE INVENTORY BEFORE REPAIR"
INV_BEFORE=$(docker compose run --rm --entrypoint python web manage.py shell -c '
from django.db.models import Sum
from core.models import Brand, StockBalance
for name in ["Novani", "دارما"]:
    b=Brand.objects.get(name=name)
    q=int(StockBalance.objects.filter(brand=b).aggregate(v=Sum("qty"))["v"] or 0)
    print(f"{name}={q}")
' 2>/dev/null) || fail "could not capture inventory before repair"
echo "$INV_BEFORE"

step "7) APPLY ONLY THE MISSING WAGE"
APPLY=$(docker compose run --rm --entrypoint python web manage.py repair_novani_wage_v34 \
  --block-id "$BLOCK_ID" \
  --expected-pieces 3160 \
  --expected-wage 26333333 \
  --apply) || fail "wage repair failed"
echo "$APPLY"
printf '%s\n' "$APPLY" | grep -q 'SUCCESS: NOVANI MISSING WAGE V34 REPAIRED; INVENTORY UNCHANGED' || fail "repair did not report success"

step "8) VERIFY INVENTORY DID NOT MOVE"
INV_AFTER=$(docker compose run --rm --entrypoint python web manage.py shell -c '
from django.db.models import Sum
from core.models import Brand, StockBalance
for name in ["Novani", "دارما"]:
    b=Brand.objects.get(name=name)
    q=int(StockBalance.objects.filter(brand=b).aggregate(v=Sum("qty"))["v"] or 0)
    print(f"{name}={q}")
' 2>/dev/null) || fail "could not capture inventory after repair"
echo "$INV_AFTER"
[ "$INV_BEFORE" = "$INV_AFTER" ] || fail "inventory changed during wage-only repair"

step "9) RECREATE LIVE WEB"
docker compose up -d --force-recreate web || fail "web recreate failed"
docker compose restart caddy || fail "caddy restart failed"
sleep 4
docker compose exec -T web python manage.py check || fail "live Django check failed"
docker compose exec -T web python manage.py check_novani_wage_v34 || fail "live Novani wage check failed"

step "10) FINAL STATE"
docker compose exec -T web python manage.py shell -c "
from core.material_report_v14 import _tailor_row
from core.models import AppSetting
r=_tailor_row(create=False)
print('TAILOR_BALANCE=', int(r.amount or 0) if r else 0)
print('REPAIR_MARKER=', AppSetting.objects.filter(key='novani_wage_repair_v34_block_${BLOCK_ID}', value='1').exists())
"

echo ""
echo "======================================"
echo "SUCCESS: NOVANI DELIVERY WAGE V34 DEPLOYED + CURRENT BLOCK REPAIRED"
echo "Backup: $BACKUP"
echo "Current Novani block: $BLOCK_ID"
echo "Missing wage deducted: 26,333,333"
echo "Inventory during repair: unchanged"
echo "Future Novani wage: based only on newly delivered pieces"
echo "Cut quantity does not create wage"
echo "======================================"
