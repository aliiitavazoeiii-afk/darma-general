#!/usr/bin/env bash
# V150: one-off Tapsi sale price, read-only tailor report, historical color yield.
# No model/schema migration or backfill. Production DB must be backed up first.
set -euo pipefail
cd /opt/darma-general
BRANCH=v150-production-yield-tapsi-tailor
BASE=d1fd87ff3a0b6e94b24de72d4c6fd4572a352a5b
fail(){ echo "STOP: $*" >&2; exit 1; }
[[ "$(git branch --show-current)" == "$BRANCH" ]] || fail "Checkout the V150 branch first"
git merge-base --is-ancestor "$BASE" HEAD || fail "V149 source ancestor missing"
git diff --quiet -- . ':(exclude)Caddyfile' || fail "Uncommitted tracked source changes"
git diff --cached --quiet -- . ':(exclude)Caddyfile' || fail "Uncommitted staged changes"
for path in core/models.py core/models_final.py core/migrations core/material_report_v23.py core/material_flow.py core/finance.py core/capital_history_v87.py core/business_tools_v62.py core/payment_source_v63.py Caddyfile; do
  git diff --quiet "$BASE"..HEAD -- "$path" || fail "Protected source changed: $path"
done
[[ -s .env ]] || fail ".env is missing"
docker compose config -q || fail "Compose config invalid"
docker compose ps --status running web | grep -q web || fail "Live web is not running"
docker compose ps --status running db | grep -q db || fail "Live DB is not running"
CADDY_BEFORE=$(sha256sum Caddyfile | awk '{print $1}')
set -a
. ./.env
set +a
mkdir -p backups
BACKUP="backups/pre-v150-features-$(date +%Y%m%d-%H%M%S).sql"
docker compose exec -T db pg_dump -U "$DB_USER" "$DB_NAME" > "$BACKUP" || fail "DB backup failed"
[[ -s "$BACKUP" ]] || fail "Empty DB backup"
echo "BACKUP=$BACKUP"
AUDIT='from django.apps import apps
from hashlib import sha256
names=["StockBalance","InventoryMovement","SaleDay","SaleLine","ProductCode","ProductSize","ProductComposition","RawMaterialStock","MaterialReportBlock","MaterialReportConsumption","MaterialReportOutputApplied","MaterialReportFabricTransfer","AppSetting","AccountEntry","BusinessPayment","DigikalaSettlement","TapsiOrder","TapsiOrderItem","TapsiStockAllocation","ExcelManualRow","TapsiPriceRule","TailorBalanceEntry"]
for name in names:
 model=apps.get_model("core",name)
 cols=[f.attname for f in model._meta.concrete_fields]
 digest=sha256()
 for row in model.objects.order_by("pk").values_list(*cols).iterator():
  digest.update(repr(row).encode("utf-8")); digest.update(b"\\n")
 print(name+"="+digest.hexdigest())'
PATTERN='^(StockBalance|InventoryMovement|SaleDay|SaleLine|ProductCode|ProductSize|ProductComposition|RawMaterialStock|MaterialReportBlock|MaterialReportConsumption|MaterialReportOutputApplied|MaterialReportFabricTransfer|AppSetting|AccountEntry|BusinessPayment|DigikalaSettlement|TapsiOrder|TapsiOrderItem|TapsiStockAllocation|ExcelManualRow|TapsiPriceRule|TailorBalanceEntry)='
TMP=$(mktemp -d /tmp/darma-v150.XXXXXX)
trap 'rm -rf "$TMP"' EXIT
docker compose exec -T web python manage.py shell -c "$AUDIT" | grep -E "$PATTERN" > "$TMP/before" || fail "Pre-deploy DB audit failed"
[[ "$(wc -l < "$TMP/before")" -eq 22 ]] || fail "Incomplete pre-deploy DB audit"
echo "=== BUILD AND CHECK WITHOUT RESTARTING LIVE SERVICES ==="
docker compose build web || fail "Build failed"
docker compose run --rm --entrypoint python web manage.py check || fail "Django check failed"
docker compose run --rm --entrypoint python web manage.py makemigrations --check --dry-run || fail "Unexpected migration changes"
docker compose run --rm --entrypoint python web manage.py migrate --check --noinput || fail "Database migration prerequisites are missing: deploy V147 schema first"
docker compose run --rm --entrypoint python web manage.py shell -c "from django.urls import reverse; from core.tailor_statement_v150 import build_tailor_statement; from core.material_report_ui_v131 import _estimate_from_yield; from decimal import Decimal; assert reverse('tailor_statement')=='/material-report/tailor-account/'; assert reverse('tailor_statement_excel')=='/material-report/tailor-account/excel/'; assert _estimate_from_yield('19.2',Decimal('37.5'))==720; data=build_tailor_statement(); assert data['opening']+data['payments']-data['wages']==data['closing']; print('V150_FEATURE_READ_ONLY=READY')" || fail "Feature preflight failed"
[[ "$(sha256sum Caddyfile | awk '{print $1}')" == "$CADDY_BEFORE" ]] || fail "Caddyfile changed"
echo "=== REPLACE WEB ONLY; NO MIGRATIONS OR BACKFILL ==="
docker compose up -d --no-deps --no-build --force-recreate web || fail "Web switch failed"
docker compose exec -T web python manage.py check || fail "Live Django check failed"
docker compose exec -T web python manage.py shell -c "from django.urls import reverse; from core.tailor_statement_v150 import build_tailor_statement; assert reverse('tailor_statement_excel'); data=build_tailor_statement(); assert data['opening']+data['payments']-data['wages']==data['closing']; print('V150_TAILOR_STATEMENT=OK')" || fail "Live feature check failed"
docker compose exec -T web python manage.py shell -c "$AUDIT" | grep -E "$PATTERN" > "$TMP/after" || fail "Post-deploy DB audit failed"
diff -u "$TMP/before" "$TMP/after" || fail "Business data changed during deployment"
[[ "$(sha256sum Caddyfile | awk '{print $1}')" == "$CADDY_BEFORE" ]] || fail "Caddyfile checksum changed"
echo "V150_FEATURES=OK"
echo "DB_UNCHANGED_ON_DEPLOY=YES"
echo "BACKUP=$BACKUP"
docker compose ps
