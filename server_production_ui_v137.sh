#!/usr/bin/env bash
# Presentation-only release. Run as: bash server_production_ui_v137.sh
# Runs in a subprocess, so a failed guard will NOT close the parent SSH session.
set -euo pipefail
cd /opt/darma-general
BASE=013f075a09f96ba7c113e8460d339453f1172263
BRANCH=v137-production-filtered-overview-and-all-time-report
fail(){ echo "STOP: $*" >&2; exit 1; }
echo "=== V137 INTEGRATED PRODUCTION UI ==="
[[ "$(git branch --show-current)" == "$BRANCH" ]] || fail "Wrong branch"
git merge-base --is-ancestor "$BASE" HEAD || fail "Takvin recovery is not preserved"
git diff --quiet -- . ':(exclude)Caddyfile' || fail "Unexpected local tracked changes"
git diff --cached --quiet -- . ':(exclude)Caddyfile' || fail "Unexpected staged changes"
git diff --quiet "$BASE"..HEAD -- core/models.py core/migrations core/material_report_v23.py core/material_report_v22.py core/material_report_v20.py core/material_flow.py core/material_color_apply_v123.py core/capital_history_v87.py core/inventory_valuation_v17.py core/business_tools_v21.py core/finance.py core/darma_cost_v55.py || fail "Protected business logic modified"
for file in $(git diff --name-only "$BASE"..HEAD); do
  case "$file" in
    core/urls.py|core/material_report_ui_v131.py|core/material_report_overall_v137.py|core/management/commands/check_production_ui_v131.py|core/test_production_workspace_v131.py|core/test_production_overall_v137.py|core/static/core/production_workspace_v131.css|core/static/core/production_workspace_v131.js|core/static/core/production_overall_v137.css|templates/core/material_report_v131.html|templates/core/material_report_overall_v137.html|.github/workflows/check-production-ui-v137.yml|server_production_ui_v137.sh) ;;
    *) fail "Unexpected changed file: $file" ;;
  esac
done
CADDY_BEFORE=$(sha256sum Caddyfile | awk '{print $1}')
docker compose config -q || fail "Invalid Docker Compose config"
docker compose ps --status running web | grep -q web || fail "Live web missing"
[[ -s .env ]] || fail ".env missing"
set -a
. ./.env
set +a
mkdir -p backups
BACKUP="backups/pre-v137-production-ui-$(date +%Y%m%d-%H%M%S).sql"
docker compose exec -T db pg_dump -U "$DB_USER" "$DB_NAME" > "$BACKUP" || fail "Database backup failed"
[[ -s "$BACKUP" ]] || fail "Empty backup"
echo "BACKUP: $BACKUP"

AUDIT='from django.apps import apps
from hashlib import sha256
names = ["StockBalance","InventoryMovement","RawMaterialStock","MaterialReportBlock","MaterialReportConsumption","MaterialReportOutputApplied","MaterialReportOutputLocation","MaterialReportColorUse","ExcelManualRow","ExcelManualSetting","BusinessPayment","AccountEntry","AppSetting","SaleLine"]
for name in names:
 model = apps.get_model("core", name)
 columns = [field.attname for field in model._meta.concrete_fields]
 digest = sha256()
 for values in model.objects.order_by("pk").values_list(*columns).iterator():
  digest.update(repr(values).encode("utf-8"))
  digest.update(b"\\n")
 print(name+"="+digest.hexdigest())'
PATTERN='^(StockBalance|InventoryMovement|RawMaterialStock|MaterialReportBlock|MaterialReportConsumption|MaterialReportOutputApplied|MaterialReportOutputLocation|MaterialReportColorUse|ExcelManualRow|ExcelManualSetting|BusinessPayment|AccountEntry|AppSetting|SaleLine)='
TMPDIR=$(mktemp -d /tmp/darma-v135.XXXXXX)
trap 'rm -rf "$TMPDIR"' EXIT
docker compose exec -T web python manage.py shell -c "$AUDIT" | grep -E "$PATTERN" > "$TMPDIR/pre" || fail "Unable to audit existing business tables"
echo "=== BUILD CANDIDATE / NO LIVE RESTART ==="
docker compose build web || fail "Image build failed; live web remains running"
docker compose run --rm --entrypoint python web manage.py check || fail "Django project check failed"
docker compose run --rm --entrypoint python web manage.py makemigrations --check --dry-run || fail "Migration drift"
docker compose run --rm --entrypoint python web manage.py check_production_ui_v131 || fail "UI contract regression"
docker compose run --rm --entrypoint python web manage.py shell -c "from django.urls import reverse; from django.test import Client; assert reverse('material_production_overall') == '/material-report/overall/'; print('OVERALL_ROUTE=ON')" || fail "Overall analytics route missing"
docker compose run --rm --entrypoint python web manage.py shell -c "$AUDIT" | grep -E "$PATTERN" > "$TMPDIR/candidate" || fail "Candidate data audit failed"
diff -u "$TMPDIR/pre" "$TMPDIR/candidate" || fail "Business data changed before switch"
[[ "$(sha256sum Caddyfile | awk '{print $1}')" == "$CADDY_BEFORE" ]] || fail "Caddyfile changed unexpectedly"
echo "=== SWITCH WEB ONLY ==="
docker compose up -d --no-deps --no-build --force-recreate web || fail "Web recreate failed"
docker compose exec -T web python manage.py check_production_ui_v131 || fail "Live UI audit failed"
docker compose exec -T web python manage.py shell -c "$AUDIT" | grep -E "$PATTERN" > "$TMPDIR/after" || fail "Post-deployment data audit failed"
diff -u "$TMPDIR/pre" "$TMPDIR/after" || fail "Protected business state unexpectedly changed"
[[ "$(sha256sum Caddyfile | awk '{print $1}')" == "$CADDY_BEFORE" ]] || fail "Caddyfile changed unexpectedly"
echo "=== COMPLETE ==="
echo "V137_UI=OK"
echo "TAKVIN_RECOVERY=PRESERVED"
echo "BUSINESS_DATA_HASHES=UNCHANGED"
echo "BACKUP=$BACKUP"
docker compose ps
