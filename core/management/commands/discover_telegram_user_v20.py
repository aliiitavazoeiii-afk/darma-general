from django.core.management.base import BaseCommand, CommandError

from core.telegram_inventory_v20 import api_call, bot_token


class Command(BaseCommand):
    help = "Print the most recent private Telegram user/chat that messaged the configured bot."

    def handle(self, *args, **options):
        if not bot_token():
            raise CommandError("TELEGRAM_BOT_TOKEN is not configured")
        try:
            me = api_call("getMe", timeout=8)
            updates = api_call("getUpdates", {"limit": "100", "timeout": "0"}, timeout=8) or []
        except Exception as exc:
            raise CommandError(f"Telegram API failed: {exc}") from exc

        candidates = []
        for update in updates:
            message = update.get("message") or (update.get("callback_query") or {}).get("message") or {}
            user = update.get("message", {}).get("from") or (update.get("callback_query") or {}).get("from") or {}
            chat = message.get("chat") or {}
            if chat.get("type") != "private" or not user.get("id"):
                continue
            candidates.append((int(update.get("update_id") or 0), user, chat))
        if not candidates:
            raise CommandError(f"No private message found for @{me.get('username', '')}. Send /start to the bot first.")
        _, user, chat = sorted(candidates, key=lambda row: row[0])[-1]
        self.stdout.write(f"BOT_USERNAME={me.get('username', '')}")
        self.stdout.write(f"TELEGRAM_USER_ID={int(user['id'])}")
        self.stdout.write(f"FIRST_NAME={user.get('first_name', '')}")
        self.stdout.write(f"USERNAME={user.get('username', '')}")
        self.stdout.write(f"CHAT_ID={int(chat.get('id') or 0)}")
