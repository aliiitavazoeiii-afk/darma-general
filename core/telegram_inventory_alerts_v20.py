import os
from collections import defaultdict
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


def _groups():
    alerts = current_alerts()
    transfer = [row for row in alerts if row["transfer_warning"]]
    production = [row for row in alerts if row["production_warning"]]
    zero = [row for row in production if int(row["total"] or 0) <= 0]
    low = [row for row in production if int(row["total"] or 0) > 0]
    transfer.sort(key=lambda row: (row["home"], row["color"].name, row["size"].sort_order, row["size"].id))
    low.sort(key=lambda row: (row["total"], row["color"].name, row["size"].sort_order, row["size"].id))
    zero.sort(key=lambda row: (row["color"].name, row["size"].sort_order, row["size"].id))
    return {
        "all": alerts,
        "transfer": transfer,
        "production": production,
        "zero": zero,
        "low": low,
    }


def _summary_markup(groups):
    rows = []
    first = []
    if groups["transfer"]:
        first.append(_button(f"📦 انتقال‌ها ({len(groups['transfer'])})", "a:transfer"))
    if groups["production"]:
        first.append(_button(f"🧵 تولید ({len(groups['production'])})", "a:production"))
    if first:
        rows.append(first)
    rows.append([_button("🏠 منوی اصلی", "m:home")])
    return _keyboard(rows)


def _detail_back_markup(extra=None):
    rows = []
    if extra:
        rows.append(extra)
    rows.append([_button("⬅️ خلاصه هشدارها", "m:alerts"), _button("🏠 منو", "m:home")])
    return _keyboard(rows)


class BatchedInventoryBot(InventoryBot):
    """Inventory bot with compact drill-down alerts; automatic alerts fire only at 09:00."""

    def send_alert_summary(self, user_id, trigger_label="وضعیت موجودی"):
        groups = _groups()
        if not groups["all"]:
            self.api.send(
                user_id,
                f"✅ {trigger_label}\nفعلاً هیچ هشدار موجودی فعالی نیست.",
                _keyboard([[_button("🏠 منوی اصلی", "m:home")]]),
            )
            return 0

        lines = [f"🚨 {trigger_label}"]
        lines.append(f"📦 انتقال به خانه: {len(groups['transfer'])} مورد")
        lines.append(f"🧵 نیاز به تولید: {len(groups['production'])} مورد")
        if groups["zero"]:
            lines.append(f"⛔ از موارد تولید، موجودی صفر: {len(groups['zero'])} مورد")
        lines.append("\nبرای جزئیات فقط یکی از دکمه‌های پایین را بزن.")
        self.api.send(user_id, "\n".join(lines), _summary_markup(groups))
        return len(groups["all"])

    def send_current_alerts(self, chat_id):
        self.send_alert_summary(chat_id, "هشدارهای فعلی دارما")

    def send_transfer_details(self, chat_id):
        groups = _groups()
        rows = groups["transfer"]
        if not rows:
            self.api.send(
                chat_id,
                f"✅ هیچ موردی برای انتقال نیست؛ موجودی خانه‌ها حداقل {home_min()} است یا خورشید موجودی قابل انتقال ندارد.",
                _detail_back_markup(),
            )
            return

        lines = [f"📦 انتقال خورشید → خانه — {len(rows)} مورد"]
        for row in rows:
            lines.append(
                f"• {row['color'].name} / {row['size'].name}: "
                f"خانه {_fmt(row['home'])} → +{_fmt(row['suggested_transfer'])}"
            )
        lines.append(f"\nهدف: رساندن موجودی خانه به {home_min()} عدد.")
        self.api.send(
            chat_id,
            "\n".join(lines),
            _detail_back_markup([_button("📦 شروع انتقال", "m:tx")]),
        )

    def send_production_details(self, chat_id):
        groups = _groups()
        production = groups["production"]
        if not production:
            self.api.send(
                chat_id,
                f"✅ هیچ هشدار تولیدی نیست؛ همه موجودی‌های کل بالاتر از {total_min()} هستند.",
                _detail_back_markup(),
            )
            return

        lines = [f"🧵 نیاز به تولید — {len(production)} مورد"]

        if groups["low"]:
            lines.append("\n🔴 کم‌موجود:")
            for row in groups["low"]:
                lines.append(
                    f"• {row['color'].name} / {row['size'].name}: کل {_fmt(row['total'])}"
                )

        if groups["zero"]:
            by_color = defaultdict(list)
            for row in groups["zero"]:
                by_color[row["color"].name].append(row["size"].name)
            lines.append("\n⛔ موجودی صفر:")
            for color_name, sizes in by_color.items():
                lines.append(f"• {color_name}: {'، '.join(sizes)}")

        lines.append(f"\nآستانه هشدار تولید: کل موجودی {total_min()} عدد یا کمتر.")
        self.api.send(chat_id, "\n".join(lines), _detail_back_markup())

    def handle_callback(self, query):
        data = query.get("data") or ""
        if data not in {"a:transfer", "a:production"}:
            return super().handle_callback(query)

        callback_id = query.get("id")
        user = query.get("from") or {}
        user_id = user.get("id")
        message = query.get("message") or {}
        chat_id = (message.get("chat") or {}).get("id")
        if callback_id:
            self.api.answer_callback(callback_id)
        if user_id is None or chat_id is None:
            return
        if not self.allowed:
            self.bootstrap_message(chat_id, user_id)
            return
        if not self.is_allowed(user_id):
            self.unauthorized(chat_id, user_id)
            return

        if data == "a:transfer":
            self.send_transfer_details(chat_id)
        else:
            self.send_production_details(chat_id)

    def send_grouped_alerts(self, trigger_label="بررسی موجودی"):
        ids = self.allowed
        if not ids:
            return 0
        sent = 0
        for user_id in ids:
            sent = max(sent, self.send_alert_summary(user_id, trigger_label))
        return sent

    def maybe_send_alerts(self, force=False):
        # The bot keeps polling for commands, but automatic stock notifications
        # are allowed only once during the 09:00 hour each day.
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
