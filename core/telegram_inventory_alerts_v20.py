import os
from datetime import datetime
from zoneinfo import ZoneInfo

from .models import AppSetting
from .telegram_inventory_bot_v20 import (
    InventoryBot,
    TelegramAPI,
    _button,
    _fmt,
    _keyboard,
    allowed_user_ids,
    current_alerts,
    home_min,
    total_min,
)


DEFAULT_ALERT_TIMEZONE = "Asia/Tehran"


def _alert_timezone():
    name = (os.getenv("TELEGRAM_ALERT_TIMEZONE") or DEFAULT_ALERT_TIMEZONE).strip()
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo(DEFAULT_ALERT_TIMEZONE)


def _now_local():
    return datetime.now(_alert_timezone())


def _marker_key(kind, target_date):
    return f"telegram_stock_alert:{kind}:{target_date.isoformat()}"


def _configured_api():
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token or not allowed_user_ids():
        return None
    return TelegramAPI(token)


class BatchedInventoryBot(InventoryBot):
    """Inventory bot with grouped alerts; automatic alerts fire only at 09:00."""

    def _send_transfer_chunks(self, user_id, rows, title=None):
        chunk_size = 12
        for start in range(0, len(rows), chunk_size):
            chunk = rows[start : start + chunk_size]
            lines = [title or f"⚠️ موجودی خانه زیر {home_min()} — انتقال از خورشید"]
            buttons = []
            for row in chunk:
                qty = int(row["suggested_transfer"] or 0)
                lines.append(
                    f"• {row['color'].name} / {row['size'].name}: خانه {_fmt(row['home'])} | "
                    f"خورشید {_fmt(row['kh'])} | پیشنهاد انتقال {_fmt(qty)}"
                )
                if qty > 0:
                    buttons.append(
                        [
                            _button(
                                f"📦 {row['color'].name} {row['size'].name} → {_fmt(qty)}",
                                f"tx:suggest:{row['size'].id}:{row['color'].id}:{qty}",
                            )
                        ]
                    )
            self.api.send(user_id, "\n".join(lines), _keyboard(buttons) if buttons else None)

    def _send_production_chunks(self, user_id, rows, title=None):
        chunk_size = 20
        for start in range(0, len(rows), chunk_size):
            chunk = rows[start : start + chunk_size]
            lines = [title or f"🧵 هشدار تولید — موجودی کل {total_min()} عدد یا کمتر"]
            for row in chunk:
                lines.append(
                    f"• {row['color'].name} / {row['size'].name}: خانه {_fmt(row['home'])} | "
                    f"خورشید {_fmt(row['kh'])} | کل {_fmt(row['total'])}"
                )
            self.api.send(user_id, "\n".join(lines))

    def send_grouped_alerts(self, trigger_label="بررسی موجودی"):
        ids = self.allowed
        if not ids:
            return 0
        alerts = current_alerts()
        transfer = [row for row in alerts if row["transfer_warning"]]
        production = [row for row in alerts if row["production_warning"]]
        for user_id in ids:
            if transfer:
                self._send_transfer_chunks(
                    user_id,
                    transfer,
                    f"⚠️ {trigger_label}\nموجودی خانه زیر {home_min()} — انتقال از خورشید",
                )
            if production:
                self._send_production_chunks(
                    user_id,
                    production,
                    f"🧵 {trigger_label}\nهشدار تولید — موجودی کل {total_min()} عدد یا کمتر",
                )
        return len(transfer) + len(production)

    def maybe_send_alerts(self, force=False):
        # Inventory is still checked while the bot is alive, but automatic Telegram
        # notifications are allowed only once during the 09:00 hour each day.
        now = _now_local()
        if now.hour != 9:
            return
        send_stock_alert_once("9am", now.date(), api=self.api, trigger_label="بررسی ساعت ۹ صبح")


def send_stock_alert_once(kind, target_date, api=None, trigger_label=None):
    ids = allowed_user_ids()
    if not ids:
        return False
    key = _marker_key(kind, target_date)
    if AppSetting.objects.filter(key=key, value="1").exists():
        return False
    api = api or _configured_api()
    if api is None:
        return False
    bot = BatchedInventoryBot(api)
    bot.send_grouped_alerts(trigger_label or "بررسی موجودی")
    AppSetting.objects.update_or_create(
        key=key,
        defaults={"value": "1", "label": f"Telegram stock alert {kind}"},
    )
    return True


def notify_after_daily_report(day):
    if not day or not day.lines.filter(quantity__gt=0).exists():
        return False
    return send_stock_alert_once(
        "after_sale",
        day.date,
        trigger_label="بعد از ثبت صورت روزانه",
    )
