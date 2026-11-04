#!/usr/bin/env bash
# Presentation-only release. Run as: bash server_production_ui_v135.sh
# Runs in a subprocess, so a failed guard will NOT close the parent SSH session.
set -euo pipefail
cd /opt/darma-general
BASE=0355e7648b1db5b03aaf5bb14d8e7b6d7f1a1a96
BRANCH=v135-new-sheet-color-and-safe-delete
fail(){ echo "STOP: $*" >&2; exit 1; }
echo "=== V135 INTEGRATED PRODUCTION UI ==="
[[ "$(git branch --show-current)" == "$BRANCH" ]] || fail "Wrong branch"
git merge-base --is-ancestor "$BASE" HEAD || fail "Takvin recovery is not preserved"
git diff --quiet -- . ':(exclude)Caddyfile' || fail "Unexpected local tracked changes"
git diff --cached --quiet -- . ':(exclude)Caddyfile' || fail "Unexpected staged changes"
git diff --quiet "$BASE"..HEAD -- core/models.py core/migrations core/material_report_v23.py core/material_report_v22.py core/material_report_v20.py core/material_flow.py core/material_color_apply_v123.py core/capital_history_v87.py core/inventory_valuation_v17.py core/business_tools_v21.py core/finance.py core/darma_cost_v55.py || fail "Protected business logic modified"
for file in $(git diff --name-only "$BASE"..HEAD); do
  case "$file" in
    core/material_report_ui_v131.py|core/management/commands/check_production_ui_v131.py|core/test_production_workspace_v131.py|core/static/core/production_workspace_v131.css|core/static/core/production_workspace_v131.js|templates/core/material_report_v131.html|.github/workflows/check-production-ui-v135.yml|server_production_ui_v135.sh) ;;
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
BACKUP="backups/pre-v135-production-ui-$(date +%Y%m%d-%H%M%S).sql"
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
echo "V135_UI=OK"
echo "TAKVIN_RECOVERY=PRESERVED"
echo "BUSINESS_DATA_HASHES=UNCHANGED"
echo "BACKUP=$BACKUP"
docker compose ps
