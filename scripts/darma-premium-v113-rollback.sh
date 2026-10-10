#!/usr/bin/env bash
set -Eeuo pipefail

# DARMA V113 reversible *runtime-only* theme rollback.
# No Git switch, no image rebuild, no database commands.
cd /opt/darma-general
STATE=/root/darma-premium-preview-v113

if [[ ! -f "$STATE/original-base.html" || ! -f "$STATE/container-id" ]]; then
  echo "ERROR: No saved pre-preview template. Nothing was changed." >&2
  exit 1
fi

expected_cid=$(cat "$STATE/container-id")
current_cid=$(docker compose ps -q web)
if [[ -z "$current_cid" || "$current_cid" != "$expected_cid" ]]; then
  echo "STOP: web container changed since preview. Do not overwrite a different release." >&2
  echo "The temporary visual patch normally disappears on web container recreation." >&2
  exit 1
fi

echo "Restoring the exact original V113 base template..."
docker cp "$STATE/original-base.html" "$current_cid:/app/templates/base.html"
# Harmless unused theme asset may remain until the next normal container rebuild.
echo "Refreshing static manifest (no migrations or data operations)..."
docker compose exec -T web python manage.py collectstatic --noinput
echo "Gracefully reloading Gunicorn workers (no container recreation)..."
docker kill --signal=HUP "$current_cid" >/dev/null
sleep 3

docker compose exec -T web python manage.py check
if ! docker exec "$current_cid" sh -c '! grep -q "darma-premium-theme.css" /app/templates/base.html'; then
  echo "ERROR: Preview stylesheet link is still present." >&2
  exit 1
fi
echo "SUCCESS: Original V113 appearance restored; business files and database untouched."
