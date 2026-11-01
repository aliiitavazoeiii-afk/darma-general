#!/bin/sh
# V131 production: UI-only, backup, protected logic diff and DB hashes.
set -eu
cd /opt/darma-general
export COMPOSE_IGNORE_ORPHANS=1
BASE=ba41d6f0479f65b3a1d72084b6ba2836fc8228a9
BRANCH=v131-production-monthly-workspace-ui
fail(){ printf '\nFAILED: %s\n' "$1"; exit 1; }
step(){ printf '\n=== %s ===\n' "$1"; }

step "V131 branch / unchanged finance and inventory guard"
test "$(git branch --show-current)" = "$BRANCH" || fail "wrong branch"
git merge-base --is-ancestor "$BASE" HEAD || fail "base v129 missing"
git diff --quiet || fail "unstaged tracked changes"
git diff --cached --quiet || fail "staged changes"
git diff --quiet "$BASE"..HEAD -- core/models.py core/models_final.py core/migrations \
    core/material_report_v23.py core/material_report_v22.py core/material_report_v20.py \
    core/material_flow.py core/material_color_apply_v123.py core/material_cost_v23.py \
    core/final_services.py core/finance.py core/capital_history_v87.py \
    core/inventory_valuation_v17.py core/darma_cost_v55.py \
    core/business_tools_v21.py core/business_tools_v62.py \
    core/inventory_operations_v16.py core/inventory_transfer_v123.py \
    || fail "protected accounting/stock/material business source changed"
CHANGED=$(git diff --name-only "$BASE"..HEAD)
for path in $CHANGED; do
  case "$path" in
    core/material_report_ui_v131.py|templates/core/material_report_v131.html|core/static/core/production_workspace_v131.css|core/static/core/production_workspace_v131.js|core/urls.py|core/test_production_workspace_v131.py|core/management/commands/check_production_ui_v131.py|.github/workflows/check-production-ui-v131.yml|server_production_ui_v131.sh) ;;
    *) fail "unexpected changed path: $path" ;;
  esac
done
git diff --quiet "$BASE"..HEAD -- Caddyfile compose.yml Dockerfile .env || fail "infrastructure files changed"

step "Backup PostgreSQL, snapshot business tables"
test -f .env || fail ".env missing"
set -a
. ./.env
set +a
docker compose config -q || fail "compose config invalid"
docker compose ps --status running web | grep -q 'web' || fail "live web not running"
mkdir -p backups
BACKUP="backups/pre-v131-production-ui-$(date +%Y%m%d-%H%M%S).sql"
docker compose exec -T db pg_dump -U "$DB_USER" "$DB_NAME" > "$BACKUP" || fail "pg_dump failed"
test -s "$BACKUP" || fail "backup file empty"
echo "BACKUP=$BACKUP"

HASH_CODE='from hashlib import sha256
from django.apps import apps
names=["StockBalance","InventoryMovement","RawMaterialStock","MaterialReportBlock","MaterialReportConsumption","MaterialReportOutputApplied","MaterialReportOutputLocation","MaterialReportColorUse","ExcelManualRow","ExcelManualSetting","BusinessPayment","AccountEntry","AppSetting","SaleLine"]
for name in names:
 m=apps.get_model("core",name)
 columns=[f.attname for f in m._meta.concrete_fields]
 h=sha256()
 for row in m.objects.order_by("pk").values_list(*columns).iterator():
  h.update(repr(row).encode("utf-8"));h.update(b"\\n")
 print(name+"="+h.hexdigest())'
HASH_PATTERN='^(StockBalance|InventoryMovement|RawMaterialStock|MaterialReportBlock|MaterialReportConsumption|MaterialReportOutputApplied|MaterialReportOutputLocation|MaterialReportColorUse|ExcelManualRow|ExcelManualSetting|BusinessPayment|AccountEntry|AppSetting|SaleLine)='
snapshot_live(){
  docker compose exec -T web python manage.py shell -c "$HASH_CODE" 2>/dev/null | grep -E "$HASH_PATTERN"
}
snapshot_candidate(){
  docker compose run --rm --entrypoint python web manage.py shell -c "$HASH_CODE" 2>/dev/null | grep -E "$HASH_PATTERN"
}
PRE=$(snapshot_live) || fail "cannot compute live pre-state hash"

step "Build candidate web image (do not restart current service)"
docker compose build web || fail "Docker build failed; current service left running"

step "Candidate static templates and read-only framework audit"
docker compose run --rm --entrypoint python web -m compileall -q core/material_report_ui_v131.py core/test_production_workspace_v131.py core/management/commands/check_production_ui_v131.py || fail "Python compile failed"
docker compose run --rm --entrypoint python web manage.py check || fail "Django check failed"
docker compose run --rm --entrypoint python web manage.py makemigrations --check --dry-run || fail "unexpected migrations"
docker compose run --rm --entrypoint python web manage.py check_production_ui_v131 || fail "new production UI contract check failed"
PROJECTED=$(snapshot_candidate) || fail "candidate database snapshot failed"
test "$PRE" = "$PROJECTED" || {
  echo "Pre-deploy data hash:"
  echo "$PRE"
  echo "Candidate data hash:"
  echo "$PROJECTED"
  fail "protected business state changed during preflight; no live switch"
}

step "Switch web container only"
docker compose up -d --no-deps --no-build --force-recreate web || fail "web recreate failed"
docker compose exec -T web python manage.py check_production_ui_v131 || fail "live UI contract check failed"
FINAL=$(snapshot_live) || fail "live final data hash failed"
test "$PRE" = "$FINAL" || {
  echo "Pre-state hash:"
  echo "$PRE"
  echo "Final hash:"
  echo "$FINAL"
  fail "data changed during UI deploy; inspect before doing any financial/stock correction"
}
docker compose ps
echo "SUCCESS: V131 MONTHLY PRODUCTION WORKSPACE DEPLOYED"
echo "UNCHANGED: posted inventory / raw-material consumption / tailoring wage / valuation"
echo "DATABASE BACKUP: $BACKUP"
