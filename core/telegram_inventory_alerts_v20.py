import os
import time
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from .digikala_zero_guard_v65 import (
    affected_variants_for_cell,
    format_preview,
    scan_zero_transitions,
    stock_cell_total,
    zero_guard_check_seconds,
)
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
    """Inventory bot with compact stock alerts plus V65 zero-stock Digikala safe preview."""

    def __init__(self, api):
        super().__init__(api)
        self.zero_guard_last_scan = 0.0
        self.zero_guard_initialized = False

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
        zero_preview = data.startswith("dkz:preview:")
        if data not in {"a:transfer", "a:production"} and not zero_preview:
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

        if zero_preview:
            try:
                _, _, size_id, color_id = data.split(":")
                cell = stock_cell_total(int(size_id), int(color_id))
                if int(cell["total"]) > 0:
                    self.api.send(
                        chat_id,
                        f"✅ موجودی {cell['color'].name} / {cell['size'].name} دیگر صفر نیست.\n"
                        f"خانه: {_fmt(cell['home'])} | خورشید: {_fmt(cell['khorshid'])} | کل: {_fmt(cell['total'])}\n"
                        "هیچ تغییری در Digikala انجام نشد.",
                        _keyboard([[_button("🏠 منوی اصلی", "m:home")]]),
                    )
                    return
                preview = affected_variants_for_cell(
                    cell["size"].id,
                    cell["color"].id,
                    force=True,
                )
                self.api.send(
                    chat_id,
                    format_preview(preview),
                    _keyboard(
                        [
                            [_button("🔒 غیرفعال‌سازی فعلاً قفل است", "m:home")],
                            [_button("🏠 منوی اصلی", "m:home")],
                        ]
                    ),
                )
            except Exception as exc:
                self.api.send(
                    chat_id,
                    f"پیش‌نمایش Digikala انجام نشد: {exc}\nهیچ تغییری در Digikala انجام نشد.",
                    _keyboard([[_button("🏠 منوی اصلی", "m:home")]]),
                )
            return

        if data == "a:transfer":
            self.send_transfer_details(chat_id)
        else:
            self.send_production_details(chat_id)

    def send_zero_guard_alert(self, chat_id, cell):
        self.api.send(
            chat_id,
            f"⛔ موجودی کل دارما صفر شد\n"
            f"{cell['color'].name} / {cell['size'].name}\n"
            f"خانه: {_fmt(cell['home'])}\n"
            f"خورشید: {_fmt(cell['khorshid'])}\n"
            f"کل: {_fmt(cell['total'])}\n\n"
            "برای ایمنی فعلاً فقط کدهای Digikala که در همین سایز به این رنگ وابسته‌اند بررسی می‌شوند. "
            "هیچ کالا خودکار غیرفعال نمی‌شود.",
            _keyboard(
                [
                    [_button("🔎 بررسی کدهای متاثر", f"dkz:preview:{cell['size'].id}:{cell['color'].id}")],
                    [_button("❌ فعلاً کاری نکن", "m:home")],
                ]
            ),
        )

    def maybe_send_zero_guard_alerts(self, force=False):
        ids = self.allowed
        if not ids:
            return
        now = time.monotonic()
        if not force and now - self.zero_guard_last_scan < zero_guard_check_seconds():
            return
        self.zero_guard_last_scan = now

        bootstrap = not self.zero_guard_initialized
        transitions = scan_zero_transitions(bootstrap=bootstrap)
        self.zero_guard_initialized = True
        if bootstrap:
            print("V65 zero guard state initialized safely; existing zero cells were not notified.", flush=True)
            return

        for cell in transitions:
            for user_id in ids:
                self.send_zero_guard_alert(user_id, cell)

    def send_grouped_alerts(self, trigger_label="بررسی موجودی"):
        ids = self.allowed
        if not ids:
            return 0
        sent = 0
        for user_id in ids:
            sent = max(sent, self.send_alert_summary(user_id, trigger_label))
        return sent

    def maybe_send_alerts(self, force=False):
        # V65 zero transitions are checked independently every ~60 seconds.
        # The pre-existing grouped production/transfer alert remains once at 09:00.
        self.maybe_send_zero_guard_alerts(force=force)
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
