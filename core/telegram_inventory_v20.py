import json
import os
import time
from datetime import date, datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Sum

from .brand_colors import colors_for_brand
from .final_services import sync_stock_transfer
from .models import AppSetting, Brand, Size, StockBalance, StockLocation, StockTransfer


BOT_VERSION = "v20"
DEFAULT_HOME_MIN = 30
DEFAULT_TOTAL_MIN = 60
DEFAULT_TIMEZONE = "Asia/Tehran"


def _env_int(key, default):
    try:
        return int(str(os.environ.get(key, default)).strip())
    except Exception:
        return int(default)


def bot_token():
    return (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()


def allowed_user_id():
    return _env_int("TELEGRAM_ALLOWED_USER_ID", 0)


def home_minimum():
    return max(0, _env_int("TELEGRAM_HOME_MIN", DEFAULT_HOME_MIN))


def total_minimum():
    return max(0, _env_int("TELEGRAM_TOTAL_MIN", DEFAULT_TOTAL_MIN))


def bot_timezone():
    name = (os.environ.get("TELEGRAM_ALERT_TIMEZONE") or DEFAULT_TIMEZONE).strip()
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo(DEFAULT_TIMEZONE)


def telegram_configured():
    return bool(bot_token() and allowed_user_id() > 0)


def api_call(method, payload=None, timeout=12, token=None):
    token = (token or bot_token()).strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    data = urlencode(payload or {}).encode("utf-8")
    request = Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        body = json.loads(response.read().decode("utf-8"))
    if not body.get("ok"):
        raise RuntimeError(body.get("description") or f"Telegram API {method} failed")
    return body.get("result")


def send_message(text, reply_markup=None, chat_id=None, disable_notification=False):
    chat_id = int(chat_id or allowed_user_id())
    if chat_id <= 0:
        raise RuntimeError("TELEGRAM_ALLOWED_USER_ID is not configured")
    payload = {
        "chat_id": str(chat_id),
        "text": str(text),
        "disable_notification": "true" if disable_notification else "false",
    }
    if reply_markup is not None:
        payload["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
    return api_call("sendMessage", payload)


def answer_callback(callback_query_id, text=""):
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text[:180]
    try:
        api_call("answerCallbackQuery", payload, timeout=5)
    except Exception:
        pass


def _button(text, callback_data):
    return {"text": text, "callback_data": callback_data}


def main_menu_markup():
    return {
        "inline_keyboard": [
            [_button("📦 انتقال خورشید ← خانه", "m:t")],
            [_button("🚨 کمبودها", "m:a"), _button("📊 موجودی", "m:i")],
            [_button("🧺 سبد انتقال", "m:b"), _button("🧾 انتقال‌های امروز", "m:r")],
        ]
    }


def _darma_objects():
    brand = Brand.objects.get(name="دارما", active=True)
    home = StockLocation.objects.get(key=StockLocation.HOME)
    kh = StockLocation.objects.get(key=StockLocation.KHORSHID)
    return brand, home, kh


def _qty(brand, color, size, location):
    return int(
        StockBalance.objects.filter(
            brand=brand, color=color, size=size, location=location
        ).aggregate(v=Sum("qty"))["v"]
        or 0
    )


def inventory_matrix():
    brand, home, kh = _darma_objects()
    sizes = list(Size.objects.all().order_by("sort_order", "id"))
    rows = []
    for color in colors_for_brand(brand):
        for size in sizes:
            home_qty = _qty(brand, color, size, home)
            kh_qty = _qty(brand, color, size, kh)
            rows.append(
                {
                    "color": color,
                    "size": size,
                    "home": home_qty,
                    "kh": kh_qty,
                    "total": home_qty + kh_qty,
                }
            )
    return rows


def stock_alert_data():
    hmin = home_minimum()
    tmin = total_minimum()
    transfer = []
    production = []
    for row in inventory_matrix():
        if row["home"] < hmin and row["kh"] > 0:
            needed = max(0, hmin - row["home"])
            move = min(needed, max(0, row["kh"]))
            if move > 0:
                transfer.append({**row, "suggested": move})
        if row["total"] <= tmin:
            production.append(row)
    return {"transfer": transfer, "production": production, "home_min": hmin, "total_min": tmin}


def _split_lines(header, lines, limit=3600):
    chunks = []
    current = header.strip()
    for line in lines:
        candidate = current + "\n" + line
        if len(candidate) > limit and current != header.strip():
            chunks.append(current)
            current = header.strip() + "\n" + line
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def stock_alert_messages(trigger_label="بررسی موجودی"):
    data = stock_alert_data()
    messages = []
    transfer = data["transfer"]
    production = data["production"]
    if transfer:
        lines = []
        for row in transfer:
            lines.append(
                f"• {row['color'].name} / {row['size'].name}: خانه {row['home']} | خورشید {row['kh']} → انتقال {row['suggested']} عدد"
            )
        messages.extend(
            _split_lines(
                f"🟠 {trigger_label}\nموجودی خانه زیر {data['home_min']} است:",
                lines,
            )
        )
    if production:
        lines = []
        for row in production:
            lines.append(
                f"• {row['color'].name} / {row['size'].name}: کل {row['total']} (خانه {row['home']} + خورشید {row['kh']})"
            )
        messages.extend(
            _split_lines(
                f"🔴 هشدار تولید\nموجودی کل به {data['total_min']} یا کمتر رسیده:",
                lines,
            )
        )
    return messages


def _marker_key(kind, target_date):
    return f"telegram_stock_{kind}_{target_date.isoformat()}"


def send_scheduled_stock_alert(kind, target_date=None, force=False):
    if not telegram_configured():
        return False
    target_date = target_date or date.today()
    key = _marker_key(kind, target_date)
    if not force and AppSetting.objects.filter(key=key, value="1").exists():
        return False
    label = "بعد از ثبت صورت روزانه" if kind == "after_sale" else "بررسی ساعت ۹ صبح"
    messages = stock_alert_messages(label)
    try:
        for text in messages:
            send_message(text, reply_markup=main_menu_markup())
        AppSetting.objects.update_or_create(
            key=key,
            defaults={"value": "1", "label": f"Telegram stock alert {kind}"},
        )
        return True
    except Exception:
        return False


def notify_after_daily_report(day):
    if not day or not day.lines.filter(quantity__gt=0).exists():
        return False
    return send_scheduled_stock_alert("after_sale", target_date=day.date)


def maybe_send_9am_alert():
    if not telegram_configured():
        return False
    now = datetime.now(bot_timezone())
    if now.hour != 9:
        return False
    return send_scheduled_stock_alert("9am", target_date=now.date())


def color_keyboard(prefix="tc"):
    brand, _, _ = _darma_objects()
    colors = list(colors_for_brand(brand))
    rows = []
    current = []
    for color in colors:
        current.append(_button(color.name, f"{prefix}:{color.id}"))
        if len(current) == 2:
            rows.append(current)
            current = []
    if current:
        rows.append(current)
    rows.append([_button("⬅️ منو", "m:home")])
    return {"inline_keyboard": rows}


def size_keyboard(color_id):
    rows = []
    current = []
    for size in Size.objects.all().order_by("sort_order", "id"):
        current.append(_button(size.name, f"ts:{color_id}:{size.id}"))
        if len(current) == 3:
            rows.append(current)
            current = []
    if current:
        rows.append(current)
    rows.append([_button("⬅️ رنگ‌ها", "m:t")])
    return {"inline_keyboard": rows}


def inventory_color_keyboard():
    return color_keyboard(prefix="ic")


def inventory_color_text(color_id):
    brand, home, kh = _darma_objects()
    color = colors_for_brand(brand).filter(id=color_id).first()
    if not color:
        return "رنگ پیدا نشد."
    lines = [f"📊 موجودی {color.name}"]
    for size in Size.objects.all().order_by("sort_order", "id"):
        h = _qty(brand, color, size, home)
        k = _qty(brand, color, size, kh)
        lines.append(f"{size.name}: خانه {h} | خورشید {k} | کل {h + k}")
    return "\n".join(lines)


def today_transfers_text():
    brand, _, _ = _darma_objects()
    today = datetime.now(bot_timezone()).date()
    qs = StockTransfer.objects.filter(
        brand=brand,
        date=today,
        note__startswith="[telegram-v20]",
    ).select_related("color", "size").order_by("id")
    if not qs.exists():
        return "🧾 امروز هنوز انتقالی با ربات ثبت نشده."
    total = 0
    lines = ["🧾 انتقال‌های امروز"]
    for row in qs:
        total += int(row.qty or 0)
        lines.append(f"• {row.color.name} / {row.size.name}: {row.qty} عدد")
    lines.append(f"جمع: {total} عدد")
    return "\n".join(lines)


def apply_transfer_basket(items, note=""):
    """items = {(color_id, size_id): qty}. Entire basket is atomic."""
    clean = {}
    for (color_id, size_id), qty in (items or {}).items():
        qty = int(qty or 0)
        if qty > 0:
            clean[(int(color_id), int(size_id))] = clean.get((int(color_id), int(size_id)), 0) + qty
    if not clean:
        raise ValueError("سبد انتقال خالی است.")

    brand, home, kh = _darma_objects()
    today = datetime.now(bot_timezone()).date()
    with transaction.atomic():
        locked = {}
        for color_id, size_id in sorted(clean):
            src, _ = StockBalance.objects.get_or_create(
                brand=brand,
                color_id=color_id,
                size_id=size_id,
                location=kh,
                defaults={"qty": 0},
            )
            src = StockBalance.objects.select_for_update().select_related("color", "size").get(pk=src.pk)
            locked[(color_id, size_id)] = src
        for key, qty in clean.items():
            src = locked[key]
            if int(src.qty or 0) < qty:
                raise ValueError(
                    f"موجودی خورشید {src.color.name} / {src.size.name} کافی نیست: فعلی {src.qty}، درخواست {qty}."
                )
        created = []
        for (color_id, size_id), qty in clean.items():
            obj = StockTransfer.objects.create(
                date=today,
                brand=brand,
                color_id=color_id,
                size_id=size_id,
                qty=qty,
                from_location=kh,
                to_location=home,
                note=f"[telegram-v20] {note}".strip(),
            )
            sync_stock_transfer(obj)
            created.append(obj)
    return created


def basket_text(basket):
    if not basket:
        return "🧺 سبد انتقال خالی است."
    brand, _, _ = _darma_objects()
    colors = {c.id: c.name for c in colors_for_brand(brand)}
    sizes = {s.id: s.name for s in Size.objects.all()}
    total = 0
    lines = ["🧺 سبد انتقال خورشید → خانه"]
    for (color_id, size_id), qty in sorted(basket.items(), key=lambda x: (colors.get(x[0][0], ""), sizes.get(x[0][1], ""))):
        total += int(qty)
        lines.append(f"• {colors.get(color_id, color_id)} / {sizes.get(size_id, size_id)}: {qty} عدد")
    lines.append(f"جمع: {total} عدد")
    return "\n".join(lines)


def basket_markup(has_items):
    rows = [[_button("➕ افزودن قلم", "m:t")]]
    if has_items:
        rows.append([_button("✅ ثبت همه انتقال‌ها", "b:ok"), _button("🗑 خالی کردن", "b:clear")])
    rows.append([_button("⬅️ منو", "m:home")])
    return {"inline_keyboard": rows}


class InventoryTelegramBot:
    def __init__(self):
        self.offset = 0
        self.basket = {}
        self.pending_qty = None

    def _authorized(self, user_id):
        return int(user_id or 0) == allowed_user_id()

    def _send_menu(self, chat_id=None):
        return send_message(
            "ربات انبار دارما\nاز منو انتخاب کن:",
            reply_markup=main_menu_markup(),
            chat_id=chat_id,
        )

    def _show_alerts(self, chat_id):
        messages = stock_alert_messages("بررسی دستی")
        if not messages:
            send_message("✅ الان هیچ هشدار موجودی فعالی وجود ندارد.", main_menu_markup(), chat_id=chat_id)
            return
        for text in messages:
            send_message(text, main_menu_markup(), chat_id=chat_id)

    def _handle_message(self, message):
        user = message.get("from") or {}
        chat = message.get("chat") or {}
        user_id = int(user.get("id") or 0)
        chat_id = int(chat.get("id") or 0)
        text = (message.get("text") or "").strip()
        if not self._authorized(user_id):
            if text.startswith("/start"):
                send_message("⛔️ این ربات خصوصی است.", chat_id=chat_id)
            return

        if self.pending_qty:
            try:
                qty = int(text.replace("٬", "").replace(",", "").strip())
            except Exception:
                qty = 0
            if qty <= 0:
                send_message("تعداد باید یک عدد بیشتر از صفر باشد. دوباره بفرست یا /cancel بزن.", chat_id=chat_id)
                return
            color_id, size_id = self.pending_qty
            brand, _, kh = _darma_objects()
            color = colors_for_brand(brand).filter(id=color_id).first()
            size = Size.objects.filter(id=size_id).first()
            if not color or not size:
                self.pending_qty = None
                send_message("رنگ یا سایز پیدا نشد.", main_menu_markup(), chat_id=chat_id)
                return
            already = int(self.basket.get((color_id, size_id), 0))
            available = _qty(brand, color, size, kh)
            if already + qty > available:
                send_message(
                    f"موجودی خورشید {color.name} / {size.name} فقط {available} عدد است و الان {already} عددش داخل سبد است.",
                    chat_id=chat_id,
                )
                return
            self.basket[(color_id, size_id)] = already + qty
            self.pending_qty = None
            send_message(basket_text(self.basket), basket_markup(True), chat_id=chat_id)
            return

        if text in {"/start", "/menu", "منو"}:
            self._send_menu(chat_id)
        elif text == "/alerts":
            self._show_alerts(chat_id)
        elif text == "/cancel":
            self.pending_qty = None
            send_message("لغو شد.", main_menu_markup(), chat_id=chat_id)
        else:
            self._send_menu(chat_id)

    def _handle_callback(self, callback):
        query_id = callback.get("id")
        user = callback.get("from") or {}
        message = callback.get("message") or {}
        chat_id = int((message.get("chat") or {}).get("id") or 0)
        user_id = int(user.get("id") or 0)
        data = callback.get("data") or ""
        if not self._authorized(user_id):
            answer_callback(query_id, "دسترسی ندارید")
            return
        answer_callback(query_id)

        if data in {"m:home", "m:menu"}:
            self._send_menu(chat_id)
        elif data == "m:t":
            send_message("رنگ را انتخاب کن:", color_keyboard(), chat_id=chat_id)
        elif data == "m:a":
            self._show_alerts(chat_id)
        elif data == "m:i":
            send_message("رنگ را برای مشاهده موجودی انتخاب کن:", inventory_color_keyboard(), chat_id=chat_id)
        elif data == "m:b":
            send_message(basket_text(self.basket), basket_markup(bool(self.basket)), chat_id=chat_id)
        elif data == "m:r":
            send_message(today_transfers_text(), main_menu_markup(), chat_id=chat_id)
        elif data.startswith("tc:"):
            color_id = int(data.split(":", 1)[1])
            send_message("سایز را انتخاب کن:", size_keyboard(color_id), chat_id=chat_id)
        elif data.startswith("ts:"):
            _, color_id, size_id = data.split(":")
            self.pending_qty = (int(color_id), int(size_id))
            brand, _, kh = _darma_objects()
            color = colors_for_brand(brand).get(id=int(color_id))
            size = Size.objects.get(id=int(size_id))
            available = _qty(brand, color, size, kh)
            send_message(
                f"{color.name} / {size.name}\nموجودی خورشید: {available}\nتعداد انتقال به خانه را به صورت عدد بفرست:",
                chat_id=chat_id,
            )
        elif data.startswith("ic:"):
            color_id = int(data.split(":", 1)[1])
            send_message(inventory_color_text(color_id), inventory_color_keyboard(), chat_id=chat_id)
        elif data == "b:clear":
            self.basket = {}
            self.pending_qty = None
            send_message("🗑 سبد خالی شد.", basket_markup(False), chat_id=chat_id)
        elif data == "b:ok":
            if not self.basket:
                send_message("سبد خالی است.", basket_markup(False), chat_id=chat_id)
                return
            send_message(
                basket_text(self.basket) + "\n\nثبت نهایی شود؟",
                {"inline_keyboard": [[_button("✅ بله، ثبت کن", "b:commit"), _button("❌ نه", "m:b")]]},
                chat_id=chat_id,
            )
        elif data == "b:commit":
            try:
                created = apply_transfer_basket(self.basket, note="ثبت از ربات تلگرام")
                count = sum(int(row.qty or 0) for row in created)
                self.basket = {}
                self.pending_qty = None
                send_message(
                    f"✅ انتقال با موفقیت ثبت شد.\n{count} عدد از خورشید به خانه منتقل شد و در سایت هم ثبت شد.",
                    main_menu_markup(),
                    chat_id=chat_id,
                )
            except Exception as exc:
                send_message(
                    f"❌ انتقال انجام نشد و هیچ قلمی ثبت نشد:\n{exc}",
                    basket_markup(bool(self.basket)),
                    chat_id=chat_id,
                )

    def process_update(self, update):
        if update.get("message"):
            self._handle_message(update["message"])
        elif update.get("callback_query"):
            self._handle_callback(update["callback_query"])

    def poll_once(self):
        result = api_call(
            "getUpdates",
            {
                "offset": str(self.offset),
                "timeout": "20",
                "allowed_updates": json.dumps(["message", "callback_query"]),
            },
            timeout=28,
        )
        for update in result or []:
            self.offset = max(self.offset, int(update.get("update_id") or 0) + 1)
            self.process_update(update)

    def run_forever(self):
        api_call(
            "setMyCommands",
            {
                "commands": json.dumps(
                    [
                        {"command": "menu", "description": "منوی اصلی"},
                        {"command": "alerts", "description": "هشدارهای موجودی"},
                        {"command": "cancel", "description": "لغو ورود تعداد"},
                    ],
                    ensure_ascii=False,
                )
            },
        )
        while True:
            try:
                maybe_send_9am_alert()
                self.poll_once()
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                print(f"telegram bot loop error: {exc}", flush=True)
                time.sleep(5)
