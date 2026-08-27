import time

from .telegram_inventory_bot_v20 import (
    InventoryBot,
    _button,
    _fmt,
    _keyboard,
    alert_check_seconds,
    alert_repeat_seconds,
    current_alerts,
    home_min,
    total_min,
)


class BatchedInventoryBot(InventoryBot):
    """InventoryBot with grouped automatic alerts instead of one Telegram message per cell."""

    def _send_transfer_chunks(self, user_id, rows):
        chunk_size = 12
        for start in range(0, len(rows), chunk_size):
            chunk = rows[start : start + chunk_size]
            lines = [f"⚠️ موجودی خانه زیر {home_min()} — انتقال از خورشید"]
            buttons = []
            for row in chunk:
                qty = int(row["suggested_transfer"] or 0)
                lines.append(
                    f"• {row['color'].name} / {row['size'].name}: خانه {_fmt(row['home'])} | "
                    f"خورشید {_fmt(row['kh'])} | پیشنهاد {_fmt(qty)}"
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

    def _send_production_chunks(self, user_id, rows):
        chunk_size = 20
        for start in range(0, len(rows), chunk_size):
            chunk = rows[start : start + chunk_size]
            lines = [f"🧵 هشدار تولید — موجودی کل {total_min()} عدد یا کمتر"]
            for row in chunk:
                lines.append(
                    f"• {row['color'].name} / {row['size'].name}: خانه {_fmt(row['home'])} | "
                    f"خورشید {_fmt(row['kh'])} | کل {_fmt(row['total'])}"
                )
            self.api.send(user_id, "\n".join(lines))

    def maybe_send_alerts(self, force=False):
        ids = self.allowed
        if not ids:
            return

        now = time.monotonic()
        if not force and now - self.last_alert_scan < alert_check_seconds():
            return
        self.last_alert_scan = now

        repeat = alert_repeat_seconds()
        alerts = current_alerts()
        active_keys = set()
        due_transfer = []
        due_production = []

        for row in alerts:
            size_id = row["size"].id
            color_id = row["color"].id

            if row["transfer_warning"]:
                key = ("home", size_id, color_id)
                active_keys.add(key)
                if now - self.last_alert_sent.get(key, 0) >= repeat:
                    due_transfer.append(row)

            if row["production_warning"]:
                key = ("production", size_id, color_id)
                active_keys.add(key)
                if now - self.last_alert_sent.get(key, 0) >= repeat:
                    due_production.append(row)

        for user_id in ids:
            if due_transfer:
                self._send_transfer_chunks(user_id, due_transfer)
            if due_production:
                self._send_production_chunks(user_id, due_production)

        for row in due_transfer:
            self.last_alert_sent[("home", row["size"].id, row["color"].id)] = now
        for row in due_production:
            self.last_alert_sent[("production", row["size"].id, row["color"].id)] = now

        for key in list(self.last_alert_sent):
            if key not in active_keys:
                self.last_alert_sent.pop(key, None)
