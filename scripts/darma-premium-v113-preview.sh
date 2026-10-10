#!/usr/bin/env bash
set -Eeuo pipefail

# DARMA V113 runtime-only premium visual preview (no build, no migrate, no seed).
# All source downloads are pinned to reviewed immutable Git commit IDs.
cd /opt/darma-general
umask 077
BASE_REF="0f2be2cc6bcd7e6753dcf9bbdbf89f4e74a98e67"
PREVIEW_REF="848d77da744e7bbcf395176b0ea8e6faa7636786"
STATE=/root/darma-premium-preview-v113

if [[ "$(git rev-parse HEAD)" != "$BASE_REF" ]]; then
  echo "STOP: Server Git HEAD is not the reviewed V113 baseline." >&2
  exit 1
fi
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "STOP: Tracked Git files have local changes; no files modified." >&2
  exit 1
fi
if [[ -f "$STATE/container-id" ]]; then
  echo "STOP: A preview backup already exists. Roll back first before retrying." >&2
  exit 1
fi

CID=$(docker compose ps -q web)
if [[ -z "$CID" || "$(docker inspect -f '{{.State.Running}}' "$CID")" != true ]]; then
  echo "STOP: Darma web container is not running." >&2
  exit 1
fi
if ! docker exec "$CID" sh -c 'tr "\000" " " </proc/1/cmdline | grep -q gunicorn'; then
  echo "STOP: PID 1 is not Gunicorn; safe HUP reload not available." >&2
  exit 1
fi

mkdir -p "$STATE"
echo "Loading reviewed UI files from Git objects; no source checkout..."
if ! git cat-file -e "$PREVIEW_REF^{commit}" 2>/dev/null; then
  echo "STOP: Preview commit not fetched. Run the provided git fetch command first." >&2
  exit 1
fi
git show "$BASE_REF:templates/base.html" > "$STATE/base-from-v113.html"
git show "$PREVIEW_REF:templates/base.html" > "$STATE/preview-base.html"
git show "$PREVIEW_REF:static/core/darma-premium-theme.css" > "$STATE/theme.css"

echo "Saving current running template for exact rollback..."
docker cp "$CID:/app/templates/base.html" "$STATE/original-base.html"
if ! cmp -s "$STATE/original-base.html" "$STATE/base-from-v113.html"; then
  echo "STOP: Running base template differs from committed V113, so preview was NOT applied." >&2
  rm -f "$STATE/original-base.html"
  exit 1
fi

# Strictly verify the preview template only adds the stylesheet link + theme class.
python3 - "$STATE/base-from-v113.html" "$STATE/preview-base.html" <<'PY'
from pathlib import Path
import sys
baseline=Path(sys.argv[1]).read_text()
preview=Path(sys.argv[2]).read_text()
needle = """</style><link rel="stylesheet" href="{% static 'core/sidebar-v72.css' %}"></head><body>"""
replacement = """</style><link rel="stylesheet" href="{% static 'core/sidebar-v72.css' %}"><link rel="stylesheet" href="{% static 'core/darma-premium-theme.css' %}?v=visual-1"></head><body class="darma-premium-theme">"""
assert baseline.count(needle)==1, "Unexpected V113 HTML marker"
assert preview == baseline.replace(needle,replacement), "Unexpected HTML change; abort"
PY

printf '%s\n' "$CID" > "$STATE/container-id"
restore_if_error() {
  status=$?
  echo "Preview failed; attempting immediate restoration..." >&2
  bash /root/darma-premium-v113-rollback.sh || true
  exit "$status"
}
trap restore_if_error ERR

echo "Applying presentation files inside the existing web container..."
docker cp "$STATE/theme.css" "$CID:/app/static/core/darma-premium-theme.css"
docker cp "$STATE/preview-base.html" "$CID:/app/templates/base.html"
echo "Collecting static theme (without database commands)..."
docker compose exec -T web python manage.py collectstatic --noinput
echo "Gracefully reloading Gunicorn; no web/db container recreation..."
docker kill --signal=HUP "$CID" >/dev/null
sleep 3

docker compose exec -T web python manage.py check
docker exec "$CID" sh -c 'grep -q "darma-premium-theme.css" /app/templates/base.html'
echo "SUCCESS: Premium visual skin applied to V113. Refresh browser with Ctrl+F5."
echo "Rollback at any time: bash /root/darma-premium-v113-rollback.sh"
