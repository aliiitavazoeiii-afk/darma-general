#!/bin/sh
set -eu
cd /opt/darma-general
fail(){ echo "FAILED: $1"; exit 1; }
BASE=36af70949a4d3d846fd824ab5d74e1af42597947
export COMPOSE_IGNORE_ORPHANS=1

echo "=== V115 BRANCH + SCOPE ==="
test "$(git branch --show-current)" = "v115-sidebar-smooth-lucide-icons" || fail "wrong branch"
git cat-file -e "$BASE^{commit}" || fail "V114 base missing"
git diff --quiet || fail "uncommitted tracked changes; stop to avoid overwriting other-chat UI work"
CHANGED=$(git diff --name-only "$BASE"..HEAD)
echo "$CHANGED"
for f in $CHANGED; do
  case "$f" in
    templates/base.html|static/core/sidebar-v115.css|core/management/commands/check_smooth_sidebar_v115.py|PROJECT_HANDOFF_CURRENT.md|docs/PROJECT_CONTEXT/README.md|docs/PROJECT_CONTEXT/64_SMOOTH_SIDEBAR_V115.md|server_smooth_sidebar_v115.sh) ;;
    *) fail "unexpected file changed: $f" ;;
  esac
done
git diff --quiet "$BASE"..HEAD -- core/models.py core/migrations core/finance.py core/material_report_v23.py core/material_report_v92.py core/calculator_v37.py core/inventory_v20.py core/sale_entry_v60.py || fail "business data/logic changed"

echo "=== BACKUP + PRE HASH ==="
docker compose config -q || fail "invalid compose"
docker compose ps --status running web | grep -q web || fail "live web not running"
test -f .env || fail ".env missing"
set -a; . ./.env; set +a
mkdir -p backups
BACKUP="backups/before-clean-sidebar-v115-$(date +%Y%m%d-%H%M%S).sql"
docker compose exec -T db pg_dump -U "$DB_USER" "$DB_NAME" > "$BACKUP" || fail "backup failed"
test -s "$BACKUP" || fail "backup empty"
HASH_CODE='from hashlib import sha256
from django.apps import apps
names=["StockBalance","InventoryMovement","RawMaterialStock","MaterialReportBlock","MaterialReportOutputApplied","MaterialReportOutputLocation","BusinessPayment","AccountEntry","SaleLine","ProductCode","ProductSize"]
for name in names:
 m=apps.get_model("core",name)
 cols=[f.attname for f in m._meta.concrete_fields]
 h=sha256()
 for row in m.objects.order_by("pk").values_list(*cols):
  h.update(repr(row).encode());h.update(b"\\n")
 print(name+"="+h.hexdigest())'
snapshot_live(){ docker compose exec -T web python manage.py shell -c "$HASH_CODE" 2>/dev/null | grep -E '^(StockBalance|InventoryMovement|RawMaterialStock|MaterialReportBlock|MaterialReportOutputApplied|MaterialReportOutputLocation|BusinessPayment|AccountEntry|SaleLine|ProductCode|ProductSize)='; }
snapshot_image(){ docker compose run --rm --entrypoint python web manage.py shell -c "$HASH_CODE" 2>/dev/null | grep -E '^(StockBalance|InventoryMovement|RawMaterialStock|MaterialReportBlock|MaterialReportOutputApplied|MaterialReportOutputLocation|BusinessPayment|AccountEntry|SaleLine|ProductCode|ProductSize)='; }
PRE=$(snapshot_live) || fail "pre snapshot failed"
echo "$PRE"

echo "=== BUILD + REGRESSIONS ==="
docker compose build web || fail "build failed"
docker compose run --rm --entrypoint python web manage.py makemigrations --check --dry-run || fail "migration drift"
docker compose run --rm --entrypoint python web manage.py check || fail "Django system check"
docker compose run --rm --entrypoint python web manage.py check_smooth_sidebar_v115 || fail "V115 navigation regression failed"
docker compose run --rm --entrypoint python web manage.py check_final_baseline_v108 || fail "V108 baseline regression failed"
docker compose run --rm --entrypoint python web manage.py check_production_unit_cost_v113 || fail "V113 cost regression failed"
PROJECTED=$(snapshot_image) || fail "projected snapshot failed"
test "$PRE" = "$PROJECTED" || { echo "$PROJECTED"; fail "pre/projected hashes differ"; }

echo "=== RECREATE WEB ==="
docker compose up -d --no-deps --force-recreate web || fail "web recreate failed"
sleep 7
docker compose exec -T web python manage.py check_smooth_sidebar_v115 || fail "live V115 regression failed"
docker compose exec -T web python manage.py check_production_unit_cost_v113 || fail "live V113 regression failed"
FINAL=$(snapshot_live) || fail "final snapshot failed"
test "$PRE" = "$FINAL" || { echo "$FINAL"; fail "pre/final hashes differ"; }

echo "SUCCESS: SMOOTH SVG SIDEBAR V115 DEPLOYED"
echo "PRE = PROJECTED = FINAL"
echo "BACKUP: $BACKUP"
