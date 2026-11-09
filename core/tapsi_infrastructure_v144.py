"""V146: Tapsi infrastructure order fee is exactly 0.3% of order gross.

IMPORTANT: A monthly platform billing floor or cap is NOT an order expense.
Never allocate 550,000 toman to a small sale or let a new order reprice earlier
orders. The posted order ledger, daily/monthly reports, receivable and capital
all use these exact same per-order costs. Historic orders with a zero snapshotted
infrastructure_percent retain zero charge.
"""
from decimal import Decimal, ROUND_HALF_UP


def _money(value):
    return int(Decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def infrastructure_allocations(orders):
    """Return per-order amounts; no DB queries, monthly redistribution or floor."""
    result = {}
    for order in orders:
        rate = Decimal(order.infrastructure_percent)
        if rate <= 0:
            result[order.pk] = 0
            continue
        gross = sum(int(item.unit_price) * int(item.quantity) for item in order.items.all())
        result[order.pk] = _money(Decimal(gross) * rate / Decimal(100))
    return result


def infrastructure_month_total(orders):
    """Informational sum of actual per-order charges; NOT monthly invoice floor."""
    return sum(infrastructure_allocations(orders).values())
