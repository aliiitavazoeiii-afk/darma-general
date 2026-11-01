#!/usr/bin/env bash
# V132 - Full production ERP checkpoint (no restores, writes, migrations or restarts).
# Repo source is delivered by GitHub; keep this script and its resulting archives OFF GitHub.
set -Eeuo pipefail
umask 077

PROJECT=/opt/darma-general
BASE=/root/darma-safe-checkpoints
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
CHECKPOINT="$BASE/production-before-redesign-$STAMP"
STAGING=
DONE=0

on_exit() {
  code=$?
  if [ "$DONE" != 1 ]; then
    printf 'CHECKPOINT_FAILED: exit=%s\n' "$code" >&2
    [ -z "$STAGING" ] || printf 'PARTIAL_BACKUP_NOT_VALID=%s\n' "$STAGING" >&2
    printf 'NO DATABASE RESTORE OR APPLICATION RESTART WAS PERFORMED\n' >&2
  fi
}
trap on_exit EXIT

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
[ "$(id -u)" -eq 0 ] || fail 'Run as root; root-only backup contains confidential data.'
[ -d "$PROJECT/.git" ] || fail 'Production Git checkout is missing.'
cd "$PROJECT"
command -v docker >/dev/null || fail 'Docker missing.'
command -v git >/dev/null || fail 'Git missing.'
command -v tar >/dev/null || fail 'tar missing.'
command -v gzip >/dev/null || fail 'gzip missing.'
command -v sha256sum >/dev/null || fail 'sha256sum missing.'
command -v python3 >/dev/null || fail 'python3 missing.'
[ -s .env ] || fail '.env missing.'
[ -f Caddyfile ] || fail 'Caddyfile missing.'
docker compose config -q || fail 'docker compose config validation failed.'
set -a
# Only source the existing production env, without displaying any contents.
. ./.env
set +a
[ -n "$DB_USER" ] && [ -n "$DB_NAME" ] || fail 'DB_USER/DB_NAME missing in .env.'

WEB_CONTAINER="$(docker compose ps -q web)"
DB_CONTAINER="$(docker compose ps -q db)"
[ -n "$WEB_CONTAINER" ] && [ -n "$DB_CONTAINER" ] || fail 'web or db container not found.'
[ "$(docker inspect -f '{{.State.Running}}' "$WEB_CONTAINER")" = true ] || fail 'web not running.'
[ "$(docker inspect -f '{{.State.Running}}' "$DB_CONTAINER")" = true ] || fail 'db not running.'
WEB_IMAGE="$(docker inspect -f '{{.Image}}' "$WEB_CONTAINER")"
WEB_IMAGE_REF="$(docker inspect -f '{{.Config.Image}}' "$WEB_CONTAINER")"
[ -n "$WEB_IMAGE" ] || fail 'Could not identify the live web image.'

mkdir -p "$BASE"
chmod 700 "$BASE"
[ ! -e "$CHECKPOINT" ] || fail 'Checkpoint path collision.'
IMAGE_BYTES="$(docker image inspect -f '{{.Size}}' "$WEB_IMAGE")"
FREE_BYTES="$(df -PB1 "$BASE" | awk 'NR==2 {print $4}')"
MIN_BYTES=$(( IMAGE_BYTES + 1073741824 ))
[ "$FREE_BYTES" -gt "$MIN_BYTES" ] || fail "Insufficient backup disk space: free=$FREE_BYTES required_above=$MIN_BYTES."
STAGING="$(mktemp -d "$BASE/.incomplete-production-$STAMP-XXXXXXXX")"
chmod 700 "$STAGING"

printf '=== PRODUCTION BACKUP V132 - READ ONLY ===\n'
printf 'CHECKPOINT_TARGET=%s\n' "$CHECKPOINT"
printf 'LIVE_WEB_IMAGE=%s\n' "$WEB_IMAGE"
printf 'STARTED_UTC=%s\n' "$(date -u --iso-8601=seconds)"

# Include every available core model that carries live stock, production, wage,
# material or payment state. Backups additionally include the *entire* database.
SNAPSHOT_CODE="$(cat <<'PY'
from hashlib import sha256
from django.apps import apps
model_names = [
  "MaterialReportBlock", "MaterialReportConsumption",
  "MaterialReportOutputApplied", "MaterialReportOutputLocation",
  "MaterialReportColorUse", "RawMaterialStock",
  "StockBalance", "InventoryMovement", "StockTransfer",
  "InventoryAdjustment", "ExcelManualRow", "ExcelManualSetting",
  "AppSetting", "BusinessPayment", "TailorBalanceEntry",
  "MaterialReportColorUse", "SaleLine", "SaleAllocation",
  "TakvinPurchase", "DigikalaSettlement", "MoneyMovement",
  "AccountEntry",
]
for model_name in sorted(set(model_names)):
    try:
        model = apps.get_model("core", model_name)
    except LookupError:
        print("MODEL_NOT_INSTALLED=" + model_name)
        continue
    columns = [f.attname for f in model._meta.concrete_fields]
    checksum = sha256()
    count = 0
    for row in model.objects.order_by("pk").values_list(*columns).iterator(chunk_size=500):
        checksum.update(repr(row).encode("utf-8"))
        checksum.update(b"\n")
        count += 1
    print("MODEL=" + model_name + " COUNT=" + str(count) + " SHA256=" + checksum.hexdigest())
PY
)"
take_snapshot() {
  docker compose exec -T web python manage.py shell -c "$SNAPSHOT_CODE" | grep -E '^(MODEL=|MODEL_NOT_INSTALLED=)' | sort
}

git rev-parse HEAD > "$STAGING/git-live-commit.txt"
git branch --show-current > "$STAGING/git-live-branch.txt"
git status --porcelain=v1 -uall > "$STAGING/git-status-before.txt"
docker compose ps --all > "$STAGING/compose-services.txt"
docker compose config --format json > "$STAGING/compose-resolved.json"
printf '%s\n' "$WEB_IMAGE" > "$STAGING/web-live-image-id.txt"
printf '%s\n' "$WEB_IMAGE_REF" > "$STAGING/web-live-image-original-reference.txt"
docker inspect "$WEB_CONTAINER" > "$STAGING/web-container-inspect.json"
docker inspect "$DB_CONTAINER" > "$STAGING/db-container-inspect.json"
docker compose exec -T web python manage.py showmigrations core > "$STAGING/core-migrations.txt"
take_snapshot > "$STAGING/economic-state-before.txt"
[ -s "$STAGING/economic-state-before.txt" ] || fail 'Pre-checkpoint economic snapshot empty.'

printf '\n[1/5] Full PostgreSQL data/schema snapshot\n'
docker compose exec -T db pg_dump -U "$DB_USER" -d "$DB_NAME" --format=custom --compress=6 --no-owner --no-acl > "$STAGING/database-complete.dump"
[ -s "$STAGING/database-complete.dump" ] || fail 'Database dump missing.'
docker compose exec -T db pg_restore --list < "$STAGING/database-complete.dump" > "$STAGING/database-restore-catalog.txt"
grep -q 'TABLE DATA' "$STAGING/database-restore-catalog.txt" || fail 'Database dump has no table data catalog.'
docker compose exec -T db pg_dumpall --globals-only -U "$DB_USER" > "$STAGING/postgres-cluster-globals.sql"
[ -s "$STAGING/postgres-cluster-globals.sql" ] || fail 'Postgres roles/globals dump failed.'

printf '\n[2/5] Current server code, local overrides, git history and config\n'
# The archive includes .env, Caddyfile, .git and any current uncommitted code.
# Existing historical backups are omitted because the full CURRENT db is saved.
tar -C "$PROJECT" \
    --exclude='./backups' \
    --exclude='./.venv' \
    --exclude='./venv' \
    --exclude='./node_modules' \
    --exclude='./.pytest_cache' \
    --exclude='./.mypy_cache' \
    --exclude='./__pycache__' \
    --exclude='*.pyc' \
    -czf "$STAGING/project-live-source-and-private-config.tar.gz" .
tar -tzf "$STAGING/project-live-source-and-private-config.tar.gz" >/dev/null

if [ -d /opt/darma-secrets/digikala/runtime ]; then
  tar -C /opt/darma-secrets -czf "$STAGING/digikala-runtime-secrets.tar.gz" digikala/runtime
  tar -tzf "$STAGING/digikala-runtime-secrets.tar.gz" >/dev/null
  printf 'DIGIKALA_RUNTIME_SECRETS=ARCHIVED\n' > "$STAGING/external-secrets-status.txt"
else
  printf 'DIGIKALA_RUNTIME_SECRETS=NOT_PRESENT\n' > "$STAGING/external-secrets-status.txt"
fi

printf '\n[3/5] Exact Docker image currently running the website\n'
docker save "$WEB_IMAGE" | gzip -1 > "$STAGING/live-web-image.tar.gz"
[ -s "$STAGING/live-web-image.tar.gz" ] || fail 'Docker image archive missing.'
gzip -t "$STAGING/live-web-image.tar.gz" || fail 'Docker image gzip integrity check failed.'

printf '\n[4/5] Verify current economic state and production code did not drift\n'
take_snapshot > "$STAGING/economic-state-after.txt"
cmp -s "$STAGING/economic-state-before.txt" "$STAGING/economic-state-after.txt" || fail 'Critical financial/stock/production data CHANGED during backup; do not call it one consistent checkpoint.'
git status --porcelain=v1 -uall > "$STAGING/git-status-after.txt"
cmp -s "$STAGING/git-status-before.txt" "$STAGING/git-status-after.txt" || fail 'Live Git worktree changed during backup.'
[ "$(docker inspect -f '{{.Image}}' "$WEB_CONTAINER")" = "$WEB_IMAGE" ] || fail 'Running web image changed while archiving.'
[ "$(docker inspect -f '{{.State.Running}}' "$WEB_CONTAINER")" = true ] || fail 'Running web stopped during checkpoint.'

printf '\n[5/5] Integrity manifest and sealed checkpoint\n'
cat > "$STAGING/RECOVERY_README.txt" <<'TXT'
V132 immutable pre-redesign checkpoint from the actual running application.
All files are PRIVATE and may contain live database records/passwords/secrets.
Never commit, push, email or publicly publish this backup directory.

This bundle includes the full CURRENT PostgreSQL DB (database-complete.dump),
PG role globals, source worktree including .git/.env/Caddyfile, the exact
currently-running web Docker image, external Digikala runtime secrets when
present, DB migration map and unchanged critical business-state snapshots.

SAFE CODE-ONLY ROLLBACK PRINCIPLE:
If redesign only changes web application code and no schema/ledger semantics,
restore the archived running image and original code, keeping the LIVE database.
An older image against newer schema is not guaranteed safe; verify migrations
and reversible schema compatibility first. Restoration may require recreating
ONLY the web container, never database/caddy/bot for a code-only rollback.

DB RESTORE IS DESTRUCTIVE:
Never restore the old SQL dump into the active production DB without a separate
fresh backup, an offline reconciliation of newer sales/payments/materials/wages,
and explicit authorization; doing so discards business transactions after
this checkpoint. Prefer revertable schema migrations and business-safe data
forward-repairs for any changes that modify production quantities/ledgers.
DO NOT automate SQL restores just because the user dislikes a redesign.
TXT
printf 'CHECKPOINT_FINISHED_UTC=%s\n' "$(date -u --iso-8601=seconds)" > "$STAGING/FINISHED.txt"
(
  cd "$STAGING"
  find . -type f ! -name SHA256SUMS.txt -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS.txt
  sha256sum --check --status SHA256SUMS.txt
)
mv "$STAGING" "$CHECKPOINT"
STAGING=
DONE=1

printf '\nSUCCESS: COMPLETE PRODUCTION CHECKPOINT CREATED\n'
printf 'BACKUP_PATH=%s\n' "$CHECKPOINT"
printf 'LIVE_WEB_IMAGE=%s\n' "$WEB_IMAGE"
printf 'GIT_COMMIT=%s\n' "$(cat "$CHECKPOINT/git-live-commit.txt")"
printf 'DATABASE_AND_INVENTORY_AND_TAILOR_LEDGER_UNCHANGED=YES\n'
printf 'RUNNING_SERVICES_RESTARTED=NO\n'
printf 'IMPORTANT: Copy this private checkpoint to a second secure machine/offsite.\n'
