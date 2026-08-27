#!/bin/sh
set -eu
cd /opt/darma-general

fail(){ echo ""; echo "======================================"; echo "FAILED: $1"; echo "======================================"; exit 1; }
step(){ echo ""; echo "======================================"; echo "$1"; echo "======================================"; }

[ -f .env ] || fail ".env not found"
set -a
. ./.env || fail "could not load .env"
set +a

[ -n "${TELEGRAM_BOT_TOKEN:-}" ] || fail "TELEGRAM_BOT_TOKEN is missing in .env"

step "1) START DATABASE"
docker compose up -d db || fail "database start failed"
i=1
while [ "$i" -le 30 ]; do
  docker compose exec -T db pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1 && break
  [ "$i" -eq 30 ] && fail "PostgreSQL did not become ready"
  sleep 1
  i=$((i+1))
done

step "2) BUILD BOT IMAGE"
docker compose -f compose.yml -f compose.telegram.yml build bot || fail "bot image build failed"

step "3) DJANGO + TELEGRAM PREFLIGHT"
docker compose -f compose.yml -f compose.telegram.yml run --rm --entrypoint python bot manage.py check || fail "Django check failed"
docker compose -f compose.yml -f compose.telegram.yml run --rm --entrypoint python bot manage.py check_telegram_bot_v20 --network || fail "Telegram bot preflight failed"

step "4) START / RECREATE BOT"
docker compose -f compose.yml -f compose.telegram.yml up -d --force-recreate bot || fail "bot start failed"

step "5) VERIFY BOT PROCESS"
sleep 2
if ! docker compose -f compose.yml -f compose.telegram.yml ps --status running bot | grep -q bot; then
  docker compose -f compose.yml -f compose.telegram.yml logs --tail=80 bot || true
  fail "bot container is not running"
fi

echo ""
echo "======================================"
echo "SUCCESS: TELEGRAM INVENTORY BOT V20 IS RUNNING"
echo "HOME low-stock threshold: ${TELEGRAM_HOME_MIN:-30}"
echo "TOTAL production threshold: ${TELEGRAM_TOTAL_MIN:-60}"
if [ -n "${TELEGRAM_ALLOWED_USER_ID:-}${TELEGRAM_ALLOWED_USER_IDS:-}" ]; then
  echo "Bot is locked to configured Telegram user ID(s)."
else
  echo "BOOTSTRAP MODE: send /whoami to the bot, copy your User ID, add TELEGRAM_ALLOWED_USER_ID=<ID> to .env, then run this script again."
fi
echo "Logs: docker compose -f compose.yml -f compose.telegram.yml logs -f --tail=100 bot"
echo "======================================"
