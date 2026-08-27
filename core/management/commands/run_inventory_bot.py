import os

from django.core.management.base import BaseCommand, CommandError

from core.telegram_inventory_bot_v20 import InventoryBot, TelegramAPI, TelegramAPIError


class Command(BaseCommand):
    help = "Run the Darma Telegram inventory transfer and stock-alert bot."

    def handle(self, *args, **options):
        token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
        if not token:
            raise CommandError("TELEGRAM_BOT_TOKEN is not set")
        try:
            InventoryBot(TelegramAPI(token)).run_forever()
        except TelegramAPIError as exc:
            raise CommandError(str(exc)) from exc
