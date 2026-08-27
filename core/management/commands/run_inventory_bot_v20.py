from django.core.management.base import BaseCommand, CommandError

from core.telegram_inventory_v20 import (
    InventoryTelegramBot,
    allowed_user_id,
    api_call,
    bot_token,
    bot_timezone,
    home_minimum,
    telegram_configured,
    total_minimum,
)


class Command(BaseCommand):
    help = "Run the private Telegram inventory bot for Darma or validate its configuration."

    def add_arguments(self, parser):
        parser.add_argument("--check", action="store_true")

    def handle(self, *args, **options):
        if not bot_token():
            raise CommandError("TELEGRAM_BOT_TOKEN is not configured")
        if allowed_user_id() <= 0:
            raise CommandError("TELEGRAM_ALLOWED_USER_ID is not configured")
        try:
            me = api_call("getMe", timeout=8)
        except Exception as exc:
            raise CommandError(f"Telegram getMe failed: {exc}") from exc

        self.stdout.write(f"BOT USERNAME = @{me.get('username', '')}")
        self.stdout.write(f"ALLOWED USER = {allowed_user_id()}")
        self.stdout.write(f"HOME MIN     = {home_minimum()}")
        self.stdout.write(f"TOTAL MIN    = {total_minimum()}")
        self.stdout.write(f"TIMEZONE     = {bot_timezone().key}")
        if not telegram_configured():
            raise CommandError("Telegram configuration is incomplete")
        if options["check"]:
            self.stdout.write(self.style.SUCCESS("TELEGRAM INVENTORY BOT V20 CONFIG OK"))
            return

        self.stdout.write(self.style.SUCCESS("TELEGRAM INVENTORY BOT V20 STARTED"))
        InventoryTelegramBot().run_forever()
