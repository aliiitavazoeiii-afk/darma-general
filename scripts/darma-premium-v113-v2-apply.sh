#!/usr/bin/env bash
set -Eeuo pipefail

# DARMA V113 Premium Skin v2 — runtime-only, reversible, same running container.
# Supports both: upgrade live v1 preview and start from untouched V113.
# Does NOT checkout a branch, build images, migrate/seed data or modify project source.
cd /opt/darma-general
umask 077
BASE="0f2be2cc6bcd7e6753dcf9bbdbf89f4e74a98e67"
V1="848d77da744e7bbcf395176b0ea8e6faa7636786"
V2="5ac356651ae97ff1f2bdd8024d3eadffe8431870"
STATE="/root/darma-premium-preview-v113"
ROLLBACK="/root/darma-premium-v113-rollback.sh"

[[ "$(git rev-parse HEAD)" == "$BASE" ]] || { echo "STOP: Git is no longer V113." >&2; exit 1; }
git diff --quiet && git diff --cached --quiet || { echo "STOP: Tracked working tree changed." >&2; exit 1; }
[[ -f "$ROLLBACK" ]] || { echo "STOP: Safe rollback script is missing." >&2; exit 1; }
git cat-file -e "$V2^{commit}" 2>/dev/null || { echo "STOP: Please run git fetch origin preview branch first." >&2; exit 1; }

CID="$(docker compose ps -q web)"
[[ -n "$CID" ]] && [[ "$(docker inspect -f '{{.State.Running}}' "$CID")" == "true" ]] || { echo "STOP: web container is not running." >&2; exit 1; }
docker exec "$CID" sh -c 'tr "\000" " " </proc/1/cmdline | grep -q gunicorn' || { echo "STOP: Gunicorn is not PID 1." >&2; exit 1; }

mkdir -p "$STATE"
git show "$BASE:templates/base.html" > "$STATE/base-from-v113.html"
git show "$V1:templates/base.html" > "$STATE/preview-base.html"
git show "$V2:static/core/darma-premium-theme.css" > "$STATE/theme-v2.css"

if [[ -f "$STATE/container-id" ]]; then
  [[ "$(cat "$STATE/container-id")" == "$CID" ]] || { echo "STOP: Web container changed. Safe live upgrade not possible." >&2; exit 1; }
  [[ -f "$STATE/original-base.html" ]] && cmp -s "$STATE/original-base.html" "$STATE/base-from-v113.html" || { echo "STOP: Original rollback copy not verified." >&2; exit 1; }
  docker cp "$CID:/app/templates/base.html" "$STATE/live-base-before-v2.html"
  cmp -s "$STATE/live-base-before-v2.html" "$STATE/preview-base.html" || { echo "STOP: Live HTML no longer matches v1 preview." >&2; exit 1; }
  echo "Confirmed v1 preview active; preserving the V113 original rollback copy."
else
  docker cp "$CID:/app/templates/base.html" "$STATE/live-base-before-v2.html"
  cmp -s "$STATE/live-base-before-v2.html" "$STATE/base-from-v113.html" || { echo "STOP: Live HTML differs from clean V113." >&2; exit 1; }
  cp "$STATE/live-base-before-v2.html" "$STATE/original-base.html"
  printf '%s\n' "$CID" > "$STATE/container-id"
  echo "Confirmed clean V113; saved original template for rollback."
fi

failed_restore(){
  status=$?
  echo "Preview v2 failed. Trying to restore V113 automatically..." >&2
  bash "$ROLLBACK" || true
  exit "$status"
}
trap failed_restore ERR

echo "Applying v2 charcoal/grain stylesheet only..."
docker cp "$STATE/theme-v2.css" "$CID:/app/static/core/darma-premium-theme.css"

if cmp -s "$STATE/live-base-before-v2.html" "$STATE/base-from-v113.html"; then
  docker cp "$STATE/preview-base.html" "$CID:/app/templates/base.html"
fi

echo "Updating static-file manifest without running migrations..."
docker compose exec -T web python manage.py collectstatic --noinput
echo "Reloading Gunicorn without Docker image or database restart..."
docker kill --signal=HUP "$CID" >/dev/null
sleep 4

docker compose exec -T web python manage.py check
docker exec "$CID" sh -c 'grep -q "darma-premium-theme.css" /app/templates/base.html'
docker exec "$CID" sh -c 'grep -q "DARMA PREMIUM" /app/static/core/darma-premium-theme.css'
echo "SUCCESS: DARMA V113 PREMIUM CHARCOAL + GRAIN V2 ACTIVE"
echo "Refresh browser with Ctrl+F5 (hard refresh)."
echo "ROLLBACK: bash /root/darma-premium-v113-rollback.sh"
