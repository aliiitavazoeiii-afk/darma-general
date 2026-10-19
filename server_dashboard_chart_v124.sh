#!/bin/sh
set -eu
cd /opt/darma-general
fail(){ echo "FAILED: $1"; exit 1; }
export COMPOSE_IGNORE_ORPHANS=1
BASE=31c81ad544f075519319efc9d6e4bdd369848371

echo "=== V124 DASHBOARD 30 PAID-SALES-DAY CHART REPAIR ==="
test "$(git branch --show-current)" = "v124-dashboard-chart-repair" || fail "wrong branch"
git cat-file -e "$BASE^{commit}" || fail "V123 parent commit missing"
git diff --quiet -- . ':(exclude)Caddyfile' || fail "other tracked local changes exist"
git diff --cached --quiet -- . ':(exclude)Caddyfile' || fail "other staged local changes exist"
git diff --quiet "$BASE"..HEAD -- Caddyfile || fail "V124 must not change Caddyfile"
test -f Caddyfile || fail "Caddyfile missing"
CADDY_BEFORE=$(sha256sum Caddyfile | awk '{print $1}')
CHANGED=$(git diff --name-only "$BASE"..HEAD)
echo "$CHANGED"
for f in $CHANGED; do
  case "$f" in
    .github/workflows/check-dashboard-v124.yml|core/excel_dashboard_v89.py|core/management/commands/check_dashboard_trend_v124.py|core/test_dashboard_chart_v124.py|docs/PROJECT_CONTEXT/72_DASHBOARD_TREND_V124.md|templates/core/dashboard_excel_v89.html|server_dashboard_chart_v124.sh) ;;
    *) fail "unexpected V124 file: $f" ;;
  esac
done
# V124 is restricted to dashboard display and date selection.
# No schema, finance, material or physical inventory edits are permitted.
git diff --quiet "$BASE"..HEAD -- \
  core/models.py core/migrations core/finance.py \
  core/excel_dashboard.py core/final_services.py \
  core/material_report_v92.py core/material_report_v23.py \
  core/material_flow.py core/wholesale_logic_v119.py \
  core/inventory_transfer_v123.py core/inventory_operations_v16.py \
  core/urls.py templates/base.html templates/core/inventory_operations.html \
  templates/core/material_report_v92.html \
  || fail "protected finance/material/schema/sidebar code modified"

echo "=== PRODUCTION PRECHECK / BACKUP ==="
docker compose config -q || fail "compose config error"
docker compose ps --status running web | grep -q web || fail "live web container not running"
test -s .env || fail ".env missing"
set -a; . ./.env; set +a
mkdir -p backups
BACKUP="backups/before-v124-dashboard-chart-$(date +%Y%m%d-%H%M%S).sql"
docker compose exec -T db pg_dump -U "$DB_USER" "$DB_NAME" > "$BACKUP" || fail "database backup failed"
test -s "$BACKUP" || fail "backup is empty"
echo "BACKUP=$BACKUP"

HASH_CODE='from hashlib import sha256
from django.apps import apps
names=["StockBalance","InventoryMovement","RawMaterialStock","MaterialReportBlock","MaterialReportOutputApplied","MaterialReportOutputLocation","BusinessPayment","AccountEntry","SaleLine","ProductCode","ProductSize","ExcelManualRow","MaterialReportConsumption"]
for name in names:
 m=apps.get_model("core",name)
 cols=[f.attname for f in m._meta.concrete_fields]
 h=sha256()
 for row in m.objects.order_by("pk").values_list(*cols):
  h.update(repr(row).encode());h.update(b"\\n")
 print(name+"="+h.hexdigest())'
# One shared regex: both running-service and candidate-image checks must
# produce an identical, ordered list of protected ERP model hashes.
SNAPSHOT_REGEX='^(StockBalance|InventoryMovement|RawMaterialStock|MaterialReportBlock|MaterialReportOutputApplied|MaterialReportOutputLocation|BusinessPayment|AccountEntry|SaleLine|ProductCode|ProductSize|ExcelManualRow|MaterialReportConsumption)='
snapshot_live(){ docker compose exec -T web python manage.py shell -c "$HASH_CODE" 2>/dev/null | grep -E "$SNAPSHOT_REGEX"; }
snapshot_image(){ docker compose run --rm --entrypoint python web manage.py shell -c "$HASH_CODE" 2>/dev/null | grep -E "$SNAPSHOT_REGEX"; }
PRE=$(snapshot_live) || fail "PRE snapshot failed"
echo "$PRE"

echo "=== READ-ONLY BUILD AND TESTS ==="
docker compose build web || fail "web build failed"
docker compose run --rm --entrypoint python web -m compileall -q core/excel_dashboard_v89.py core/management/commands/check_dashboard_trend_v124.py core/test_dashboard_chart_v124.py || fail "Python syntax check failed"
docker compose run --rm --entrypoint python web manage.py makemigrations --check --dry-run || fail "unexpected database schema migration"
docker compose run --rm --entrypoint python web manage.py check || fail "Django project check failed"
docker compose run --rm --entrypoint python web manage.py showmigrations core | grep -Eq '\[X\] 0021_material_color_use_v123' || fail "V123 migration not applied (earlier V123 deploy needed)"
docker compose run --rm --entrypoint python web manage.py check_dashboard_trend_v124 || fail "V124 dashboard trend check failed"
docker compose run --rm --entrypoint python web manage.py check_material_transfer_v123 || fail "Inherited V123 report/warehouse check failed"
docker compose run --rm --entrypoint python web manage.py check_material_summary_box_grid_v110 || fail "Inherited material summary check failed"
docker compose run --rm --entrypoint python web manage.py check_ui_rail_report_v116 || fail "Sidebar/UI check failed"
docker compose run --rm --entrypoint python web manage.py check_wholesale_v119 || fail "Wholesales/ledger check failed"
PROJECTED=$(snapshot_image) || fail "PROJECTED snapshot failed"
test "$PRE" = "$PROJECTED" || { echo "$PROJECTED"; fail "business data changed during image preflight"; }

test "$(sha256sum Caddyfile | awk '{print $1}')" = "$CADDY_BEFORE" || fail "Caddyfile changed"
echo "=== RECREATE WEB ONLY ==="
docker compose up -d --no-deps --force-recreate web || fail "web restart failed"
sleep 6
docker compose exec -T web python manage.py check_dashboard_trend_v124 || fail "Live dashboard trend audit failed"
docker compose exec -T web python manage.py check_material_transfer_v123 || fail "Live V123 audit failed"
docker compose exec -T web python manage.py check_wholesale_v119 || fail "Live wholesale/financial audit failed"
FINAL=$(snapshot_live) || fail "FINAL snapshot failed"
test "$PRE" = "$FINAL" || { echo "$FINAL"; fail "business data changed during deployment"; }
test "$(sha256sum Caddyfile | awk '{print $1}')" = "$CADDY_BEFORE" || fail "Caddyfile changed during deployment"
echo "SUCCESS: V124 DASHBOARD SALES TREND DEPLOYED"
echo "PRE = PROJECTED = FINAL"
echo "BACKUP=$BACKUP"
