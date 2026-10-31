#!/bin/sh
set -eu
cd /opt/darma-general
fail(){ echo "FAILED: $1"; exit 1; }
export COMPOSE_IGNORE_ORPHANS=1
BASE=f3323ef155c1ccc7290512f2a82cdc01ac060d2c

echo "=== V131 DEPLOY AUDITED TAKVIN RECOVERY COMMAND, NO MONEY REPAIR ==="
test "$(git branch --show-current)" = "v131-takvin-deleted-payment-recovery" || fail "wrong branch"
git cat-file -e "$BASE^{commit}" || fail "V130 parent commit missing"
git diff --quiet -- . ':(exclude)Caddyfile' || fail "other tracked local changes exist"
git diff --cached --quiet -- . ':(exclude)Caddyfile' || fail "other staged local changes exist"
git diff --quiet "$BASE"..HEAD -- Caddyfile || fail "V131 must not change Caddyfile"
test -f Caddyfile || fail "Caddyfile missing"
CADDY_BEFORE=$(sha256sum Caddyfile | awk '{print $1}')
CHANGED=$(git diff --name-only "$BASE"..HEAD)
echo "$CHANGED"
for f in $CHANGED; do
  case "$f" in
    .github/workflows/check-takvin-recovery-v131.yml|PROJECT_HANDOFF_CURRENT.md|core/management/commands/recover_takvin_deleted_50m_v131.py|core/test_takvin_recovery_v131.py|docs/PROJECT_CONTEXT/82_TAKVIN_DELETED_PAYMENT_RECOVERY_V131.md|docs/PROJECT_CONTEXT/README.md|server_takvin_recovery_v131.sh) ;;
    *) fail "unexpected V131 file: $f" ;;
  esac
done
# Production ERP data, finance, materials synchronization, stock and all
# existing HTML sidebar/business templates MUST be identical to V121.
git diff --quiet "$BASE"..HEAD -- \
    core/material_receipt_sync.py core/material_flow.py core/wholesale_logic_v119.py \
    core/business_tools_v14.py core/capital_history_v87.py \
    core/finance_overview_v104.py core/sale_entry_v60.py templates/base.html \
    core/final_services.py core/models.py core/urls.py \
    core/material_report_v23.py core/material_report_v20.py \
    core/material_color_apply_v123.py \
    core/material_purchase_v13.py core/material_payment_colors_v124.py \
    core/inventory_v20.py templates/core/inventory_v19.html \
    templates/core/material_report_v36.html || fail "protected business/inventory logic changed"
# Pin both exact approved warning-only files. This prevents a later
# unreviewed change to stock quantities, valuation, or HTML from passing this
# release simply because inventory_v20.py is now allowlisted.
test "$(git hash-object core/inventory_v20.py)" = "2363028c157e0ed95b41559dfffa94a98f9010d2" || fail "inventory source does not match approved zero/under-ten warning-only revision"
test "$(git hash-object templates/core/inventory_v19.html)" = "ee2171ef85a8be431da59824b56b438c5ad4e05c" || fail "inventory HTML does not match approved warning-only presentation revision"

# V125 modifies only the previously approved historic materials report
# presentation and read-side aggregation; pin exact two files.
test "$(git hash-object core/material_report_v92.py)" = "28def6ba0268c31b759fce107f36102baa1d10bc" || fail "material archive month report Python source drift"
test "$(git hash-object templates/core/material_report_v92.html)" = "120803312b9881b62bf37b0649d3101b00f44db7" || fail "material archive month report UI drift"

# Only the three approved payment color source files may modify payment
# behavior. Their pinned blobs lock the price, bank, raw-stock and editing
# formulas until another reviewed deployment updates these checks.
test "$(git hash-object core/material_payment_colors_v124.py)" = "380f7f8c3d4f0aaceba6a1c6685fd094be33c194" || fail "material color helper drift"
# V126 changes ONLY read-side payment filters/row decorators; these exact
# approved blobs prevent modification of posting, cash or material balances.
test "$(git hash-object core/business_tools_v91.py)" = "0aa95daa6fe58d8a3860c4b094f9c87aea2e7254" || fail "payment filter view drift"
test "$(git hash-object core/business_tools_v60.py)" = "e9dc85c0d9ec336f014daf6b5cb3b1718b9d2c43" || fail "payment row presentation drift"
test "$(git hash-object core/business_tools_v62.py)" = "7e51ddcb1996e002b4f52b3409bb9cd55874f9f0" || fail "payment source row presentation drift"
test "$(git hash-object core/material_purchase_v13.py)" = "cac0f262ab3df38c7d92d254469541a93eb5e8e4" || fail "purchase parser drift"
test "$(git hash-object core/business_tools_v21.py)" = "d1ee5abd7fba087d135b3d0cf6ef1aaee5b20c1b" || fail "signed Takvin payment source drift"
test "$(git hash-object templates/core/_finance_kpis_v104.html)" = "02f9b0df63a0ae2e915905e5dee94b36fe9d5b60" || fail "Takvin signed balance KPI drift"
test "$(git hash-object templates/core/finance_accounts_v97.html)" = "8cd86545173f534a761f43af256ff15349b0509c" || fail "Takvin signed balance accounts UI drift"
git diff --quiet "$BASE"..HEAD -- core/models.py core/migrations core/material_report_v23.py core/material_flow.py core/material_purchase_v14.py core/material_purchase_v60.py core/inventory_v20.py core/wholesale_logic_v119.py core/final_services.py templates/core/payments_v22.html templates/core/_payment_edit_v22.html || fail "protected finance, material posting, inventory, or payment template changed"

# The only altered transfer, CSRF and browser transport source files are pinned
# to the audited branch blobs. Prevent an unreviewed ledger or auth change.
test "$(git hash-object config/settings.py)" = "f575fd81b74f0beff2b726fe3e99ea69d11f86d7" || fail "CSRF settings drift"
test "$(git hash-object core/inventory_operations_v16.py)" = "28207eefde868c5a03296f57bbe17828892c63ed" || fail "canonical route dispatch source drift"
test "$(git hash-object core/inventory_transfer_v123.py)" = "ddf8b9ddd15c158224a74ecb3926fb55612163a6" || fail "transfer endpoint drift"
test "$(git hash-object templates/core/inventory_operations.html)" = "96a0d9879b5c9ff7e1f3fbdac0258987492d0bd5" || fail "transfer browser UI drift"
# Build-only resilience and privacy fixes. Do not let a changed Dockerfile
# or .dockerignore silently enter the production image.
test "$(git hash-object Dockerfile)" = "5412293d17c7ff736406cdfac71cbb367cc49614" || fail "Dockerfile pip timeout pin drift"
test "$(git hash-object .dockerignore)" = "b18e1b1fe92a87a35341f1f26ca30d55f8e069f5" || fail "Docker context exclusion rules drift"

MIGRATION_CHANGED=$(git diff --name-only "$BASE"..HEAD -- core/migrations)
test -z "$MIGRATION_CHANGED" || fail "V131 must not introduce migrations"

echo "=== PRODUCTION PRECHECK / BACKUP ==="
docker compose config -q || fail "compose config error"
docker compose ps --status running web | grep -q web || fail "live web container not running"
test -s .env || fail ".env missing"
set -a; . ./.env; set +a
mkdir -p backups
BACKUP="backups/before-v131-takvin-recovery-$(date +%Y%m%d-%H%M%S).sql"
docker compose exec -T db pg_dump -U "$DB_USER" "$DB_NAME" > "$BACKUP" || fail "database backup failed"
test -s "$BACKUP" || fail "backup is empty"
echo "BACKUP=$BACKUP"

HASH_CODE='from hashlib import sha256
from django.apps import apps
names=["ExcelManualSetting","TakvinPurchase","StockBalance","InventoryMovement","StockTransfer","InventoryAdjustment","RawMaterialStock","MaterialReportBlock","MaterialReportOutputApplied","MaterialReportOutputLocation","MaterialReportColorUse","BusinessPayment","AccountEntry","MoneyMovement","DigikalaSettlement","SaleLine","ProductCode","ProductSize","ExcelManualRow","MaterialReportConsumption","WholesaleInvoice","WholesaleReceipt","TailorBalanceEntry"]
for name in names:
 m=apps.get_model("core",name)
 cols=[f.attname for f in m._meta.concrete_fields]
 h=sha256()
 for row in m.objects.order_by("pk").values_list(*cols):
  h.update(repr(row).encode());h.update(b"\\n")
 print(name+"="+h.hexdigest())'
# One shared regex: both running-service and candidate-image checks must
# produce an identical, ordered list of protected ERP model hashes.
SNAPSHOT_REGEX='^(StockBalance|InventoryMovement|StockTransfer|InventoryAdjustment|RawMaterialStock|MaterialReportBlock|MaterialReportOutputApplied|MaterialReportOutputLocation|MaterialReportColorUse|BusinessPayment|AccountEntry|MoneyMovement|DigikalaSettlement|SaleLine|ProductCode|ProductSize|ExcelManualRow|MaterialReportConsumption|WholesaleInvoice|WholesaleReceipt|TailorBalanceEntry)='
snapshot_live(){ docker compose exec -T web python manage.py shell -c "$HASH_CODE" 2>/dev/null | grep -E "$SNAPSHOT_REGEX"; }
snapshot_image(){ docker compose run --rm --entrypoint python web manage.py shell -c "$HASH_CODE" 2>/dev/null | grep -E "$SNAPSHOT_REGEX"; }
PRE=$(snapshot_live) || fail "PRE snapshot failed"
echo "$PRE"

echo "=== READ-ONLY BUILD AND TESTS ==="
# The live server may reach Docker Hub manifest metadata but receive HTTP
# 403 when retrieving Python layers from Docker Hub's CloudFront CDN.
# Never edit the tracked Dockerfile, Docker daemon configuration or Caddyfile.
# If and ONLY if the base-image retrieval fails, try trusted mirrors with a
# temporary equivalent Dockerfile and tag the exact Compose web image.
echo "=== V129 SAFE DOCKER BUILD / PYPI RETRIES ==="
BUILD_LOG=$(mktemp /tmp/darma-v131-build-log.XXXXXX)
TEMP_DOCKERFILE=$(mktemp /tmp/darma-v131-Dockerfile.XXXXXX)
trap 'rm -f "$BUILD_LOG" "$TEMP_DOCKERFILE"' EXIT
# Transient PyPI wheel-download timeouts are not base-image registry errors.
# Retry the unchanged pinned Dockerfile at most three times. Do not restart
# the live web container unless a complete verified build succeeds.
BUILD_OK=0
for BUILD_ATTEMPT in 1 2 3; do
  echo "DOCKER_WEB_BUILD_ATTEMPT=$BUILD_ATTEMPT/3"
  if docker compose build web >"$BUILD_LOG" 2>&1; then
    cat "$BUILD_LOG"
    echo "DOCKER_BASE_IMAGE_SOURCE=docker_hub"
    BUILD_OK=1
    break
  fi
  cat "$BUILD_LOG"
  if grep -Eq 'ReadTimeoutError|Read timed out|The read operation timed out|files\.pythonhosted\.org.*timed out' "$BUILD_LOG"; then
    if [ "$BUILD_ATTEMPT" -lt 3 ]; then
      echo "PYPI_READ_TIMEOUT_RETRY=$BUILD_ATTEMPT"
      sleep 5
      continue
    fi
    fail "PyPI wheel download timed out after three safe builds; live web remains unchanged"
  fi
  # Preserve the previously approved trusted base-image mirrors ONLY when
  # the Docker Hub image itself failed; do not use mirrors for PyPI problems.
  if ! grep -Eq 'failed to resolve source metadata|production.cloudfront.docker.com|unexpected status.*403|403 Forbidden' "$BUILD_LOG"; then
    fail "Docker build failed for a reason other than base-image registry access or PyPI timeout; current web remains unchanged"
  fi
  test "$(head -n 1 Dockerfile)" = "FROM python:3.12-slim" || fail "unexpected tracked Dockerfile base; refusing mirror substitution"
  WEB_IMAGE=$(docker compose config --format json | python3 -c 'import json,sys; c=json.load(sys.stdin); web=c["services"]["web"]; print(web.get("image") or (c["name"]+"-web"))') || fail "cannot determine Compose web image name"
  test -n "$WEB_IMAGE" || fail "empty Compose web image name"
  MIRROR_OK=0
  for PYTHON_BASE in public.ecr.aws/docker/library/python:3.12-slim mirror.gcr.io/library/python:3.12-slim; do
    echo "TRY_ALTERNATE_PYTHON_BASE=$PYTHON_BASE"
    { printf 'FROM %s\n' "$PYTHON_BASE"; tail -n +2 Dockerfile; } > "$TEMP_DOCKERFILE"
    if docker buildx build --load --progress=plain -f "$TEMP_DOCKERFILE" -t "$WEB_IMAGE" .; then
      MIRROR_OK=1
      echo "DOCKER_BASE_IMAGE_SOURCE=$PYTHON_BASE"
      break
    fi
  done
  test "$MIRROR_OK" = "1" || fail "Docker Hub returned 403 and alternate public registries were also inaccessible; no web restart performed"
  BUILD_OK=1
  break
done
test "$BUILD_OK" = "1" || fail "Docker web build did not complete; live web remains unchanged"
docker compose run --rm --entrypoint python web -m compileall -q core/material_report_v92.py core/material_report_v23.py core/material_report_v20.py core/material_color_apply_v123.py core/material_color_models_v123.py core/inventory_transfer_v123.py core/inventory_operations_v16.py core/migrations/0021_material_color_use_v123.py core/management/commands/check_material_transfer_v123.py core/management/commands/check_inventory_alert_v123.py core/material_payment_colors_v124.py core/business_tools_v91.py core/material_purchase_v13.py core/management/commands/check_payment_colors_v124.py core/management/commands/check_material_archive_month_v125.py core/management/commands/check_payment_filters_v126.py core/management/commands/check_receipt_filters_v91.py core/business_tools_v60.py core/business_tools_v62.py core/inventory_v20.py core/test_material_color_v123.py core/test_transfer_transport_v127.py core/management/commands/check_transfer_transport_v127.py core/test_transfer_same_page_v128.py core/management/commands/check_transfer_same_page_v128.py core/test_transfer_form_action_v129.py core/management/commands/check_transfer_form_action_v129.py core/business_tools_v21.py core/test_takvin_signed_payment_v130.py core/management/commands/check_takvin_signed_v130.py core/test_takvin_recovery_v131.py core/management/commands/recover_takvin_deleted_50m_v131.py config/settings.py || fail "Python syntax check failed"
docker compose run --rm --entrypoint python web manage.py makemigrations --check --dry-run || fail "unexpected database schema migration"
docker compose run --rm --entrypoint python web manage.py check || fail "Django project check failed"
docker compose run --rm --entrypoint python web manage.py showmigrations core | grep -Eq '\[X\] 0021_material_color_use_v123' || fail "V123 per-color migration missing; deploy V123 first"
# V121 account repair must be reviewed/finished separately. Never change it
# as a side effect of a materials report-only release.
REPAIR_AUDIT=$(docker compose run --rm --entrypoint python web manage.py repair_pedram_wholesale_v121) || fail "financial state preview failed"
echo "$REPAIR_AUDIT"
printf '%s\n' "$REPAIR_AUDIT" | grep -qx 'PEDRAM_REPAIR_GROSS=0' || fail "V121 Pedram repair still pending; complete approved recovery before V124"

echo "=== V131 READ-ONLY TAKVIN RECOVERY PREFLIGHT (DOES NOT APPLY REPAIR) ==="
docker compose run --rm --entrypoint python web manage.py recover_takvin_deleted_50m_v131 --bank melat --paid-on 2026-10-29 || fail "V131 strict no-write dry-run failed"
docker compose run --rm --entrypoint python web manage.py check_takvin_signed_v130 || fail "V130 Takvin read-only audit failed"
docker compose run --rm --entrypoint python web manage.py check_transfer_form_action_v129 || fail "V129 shadowed form action read-only audit failed"
docker compose run --rm --entrypoint python web manage.py check_transfer_same_page_v128 || fail "V128 canonical AJAX route audit failed"
docker compose run --rm --entrypoint python web manage.py check_transfer_transport_v127 || fail "V127 JSON 401/403 transfer transport read-only audit failed"
docker compose run --rm --entrypoint python web manage.py check_payment_filters_v126 || fail "V126 all-time payment totals and inclusive Jalali date filter failed"
docker compose run --rm --entrypoint python web manage.py check_receipt_filters_v91 || fail "V91 receipt filters regression failed"
docker compose run --rm --entrypoint python web manage.py check_material_archive_month_v125 || fail "V125 selected Jalali archive and per-color remaining deliveries failed"
docker compose run --rm --entrypoint python web manage.py check_payment_colors_v124 || fail "V124 registered payment colors audit failed"
docker compose run --rm --entrypoint python web manage.py check_material_transfer_v123 || fail "V123 material/inventory read-only audit failed"
docker compose run --rm --entrypoint python web manage.py check_inventory_alert_v123 || fail "V123 inventory warning threshold verification failed"

docker compose run --rm --entrypoint python web manage.py check_material_net_v122 || fail "V122 net/month+carryover verification failed"
docker compose run --rm --entrypoint python web manage.py check_material_summary_box_grid_v110 || fail "V110+V118 UI check failed"
docker compose run --rm --entrypoint python web manage.py check_fabric_roll_count_v116 || fail "V118 fabric roll/weight check failed"
docker compose run --rm --entrypoint python web manage.py check_ui_rail_report_v116 || fail "sidebar regression failed"
docker compose run --rm --entrypoint python web manage.py check_wholesale_v119 || fail "wholesale accounting regression failed"
docker compose run --rm --entrypoint python web manage.py check_production_unit_cost_v113 || fail "calculator regression failed"
PROJECTED=$(snapshot_image) || fail "PROJECTED snapshot failed"
test "$PRE" = "$PROJECTED" || { echo "$PROJECTED"; fail "business data changed during image preflight"; }

test "$(sha256sum Caddyfile | awk '{print $1}')" = "$CADDY_BEFORE" || fail "Caddyfile changed"
echo "=== RECREATE WEB ONLY ==="
docker compose up -d --no-deps --no-build --force-recreate web || fail "web restart failed"
sleep 6
docker compose exec -T web python manage.py recover_takvin_deleted_50m_v131 --bank melat --paid-on 2026-10-29 || fail "live V131 no-write dry-run failed"
docker compose exec -T web python manage.py check_takvin_signed_v130 || fail "live V130 Takvin read-only audit failed"
docker compose exec -T web python manage.py check_transfer_form_action_v129 || fail "live V129 form action read-only audit failed"
docker compose exec -T web python manage.py check_transfer_same_page_v128 || fail "live V128 same-page route audit failed"
docker compose exec -T web python manage.py check_transfer_transport_v127 || fail "live V127 transport audit failed"
docker compose exec -T web python manage.py check_payment_filters_v126 || fail "live V126 payment totals and date filters failed"
docker compose exec -T web python manage.py check_receipt_filters_v91 || fail "live V91 receipt filters failed"
docker compose exec -T web python manage.py check_material_archive_month_v125 || fail "live V125 Jalali archive month audit failed"
docker compose exec -T web python manage.py check_payment_colors_v124 || fail "live V124 color validation failed"
docker compose exec -T web python manage.py check_material_transfer_v123 || fail "live V123 audit failed"
docker compose exec -T web python manage.py check_inventory_alert_v123 || fail "live V123 warning threshold verification failed"
docker compose exec -T web python manage.py check_material_net_v122 || fail "live V122 verification failed"
docker compose exec -T web python manage.py check_material_summary_box_grid_v110 || fail "live V110 report regression failed"
docker compose exec -T web python manage.py check_fabric_roll_count_v116 || fail "live V118 fabric regression failed"
docker compose exec -T web python manage.py check_wholesale_v119 || fail "live V119 finance regression failed"
FINAL=$(snapshot_live) || fail "FINAL snapshot failed"
test "$PRE" = "$FINAL" || { echo "$FINAL"; fail "business data changed during deployment"; }
test "$(sha256sum Caddyfile | awk '{print $1}')" = "$CADDY_BEFORE" || fail "Caddyfile changed during deployment"
echo "SUCCESS: V131 READ-ONLY TAKVIN RECOVERY COMMAND DEPLOYED (NO BALANCE REPAIR)"
echo "PRE = PROJECTED = FINAL"
echo "BACKUP=$BACKUP"
