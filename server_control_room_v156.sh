#!/usr/bin/env bash
# V156: backup first; no migration, DB mutation, existing business module edits.
# Web-only deployment for standalone, GET-only Control Room.
set -euo pipefail
cd /opt/darma-general
BASE=36921a88560fe21a7bea5f633872cc31ae4f89ed
BRANCH=v156-readonly-control-room
fail(){ echo "STOP: $*" >&2; exit 1; }
echo "=== V156 READ-ONLY CONTROL ROOM DEPLOY ==="
[[ "$(git branch --show-current)" == "$BRANCH" ]] || fail "Wrong branch"
git merge-base --is-ancestor "$BASE" HEAD || fail "V155 ancestor missing"
git diff --quiet -- . ':(exclude)Caddyfile' || fail "Unexpected tracked source modifications"
git diff --cached --quiet -- . ':(exclude)Caddyfile' || fail "Unexpected staged modifications"
for f in $(git diff --name-only "$BASE"..HEAD); do
  case "$f" in
    core/control_room_v156.py|core/test_control_room_v156.py|templates/core/control_room_v156.html|core/urls.py|templates/base.html|.github/workflows/check-control-room-v156.yml|server_control_room_v156.sh) ;;
    *) fail "Unexpected change outside isolated module: $f" ;;
  esac
done
[[ -s .env ]] || fail ".env is missing"
docker compose config -q || fail "Docker config invalid"
docker compose ps --status running web | grep -q web || fail "Web not running"
docker compose ps --status running db | grep -q db || fail "DB not running"
CADDY_BEFORE=$(sha256sum Caddyfile | awk '{print $1}')
set -a
. ./.env
set +a
mkdir -p backups
BACKUP="backups/pre-v156-control-room-$(date +%Y%m%d-%H%M%S).sql"
docker compose exec -T db pg_dump -U "$DB_USER" "$DB_NAME" > "$BACKUP" || fail "Postgres backup failed"
[[ -s "$BACKUP" ]] || fail "Backup empty"
echo "BACKUP=$BACKUP"
echo "=== BUILD CANDIDATE WITHOUT RESTART ==="
docker compose build web || fail "Build failed"
docker compose run --rm --entrypoint python web manage.py check || fail "Django check failed"
docker compose run --rm --entrypoint python web manage.py makemigrations --check --dry-run || fail "Migration drift"
docker compose run --rm --entrypoint python web manage.py migrate --check --noinput || fail "Unexpected migrations"
docker compose run --rm --entrypoint python web manage.py shell -c "from django.urls import reverse; from django.template.loader import get_template; assert reverse('control_room')=='/control-room/'; get_template('core/control_room_v156.html'); print('V156_TEMPLATE_ROUTE=PASS')" || fail "Template/route check failed"
[[ "$(sha256sum Caddyfile | awk '{print $1}')" == "$CADDY_BEFORE" ]] || fail "Caddyfile modified"
echo "=== WEB-ONLY SWITCH ==="
docker compose up -d --no-deps --no-build --force-recreate web || fail "Web update failed"
docker compose exec -T web python manage.py check || fail "Live Django check failed"
docker compose exec -T web python manage.py shell -c "from django.urls import reverse; from django.template.loader import get_template; assert reverse('control_room')=='/control-room/'; get_template('core/control_room_v156.html'); print('V156_LIVE_ROOM=READY')" || fail "Live room not available"
[[ "$(sha256sum Caddyfile | awk '{print $1}')" == "$CADDY_BEFORE" ]] || fail "Caddyfile altered"
echo "V156_CONTROL_ROOM=READY"
echo "V156_NO_MIGRATIONS_NO_BUSINESS_DATA_WRITES=YES"
echo "BACKUP=$BACKUP"
docker compose ps
