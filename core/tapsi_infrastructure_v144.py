"""Tapsi infrastructure settlement: 0.3% of monthly gross, min 550k, max 2.2m.

Never charge a monthly minimum per order. Apply exactly ONE monthly expense
whenever that Persian month contains V144-eligible orders, and attribute it
deterministically across eligible orders in proportion to their recorded sales.
Old orders carry infrastructure_percent=0 and remain completely unchanged.

This is a provisional accrued monthly charge (not a bank debit, not settlement).
It may be reallocated within the open month as additional orders arrive.
"""
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

import jdatetime
from django.db.models import Prefetch

from .models import TapsiOrder

MONTHLY_MINIMUM = 550_000
MONTHLY_MAXIMUM = 2_200_000


def _money(decimal_value):
    return int(Decimal(decimal_value).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def jalali_month_bounds(day):
    j = jdatetime.date.fromgregorian(date=day)
    first = jdatetime.date(j.year, j.month, 1)
    nxt = jdatetime.date(j.year + 1, 1, 1) if j.month == 12 else jdatetime.date(j.year, j.month + 1, 1)
    return first.togregorian(), nxt.togregorian() - timedelta(days=1)


def infrastructure_month_total(eligible_orders):
    """Monthly platform invoice accrual; positive even if percent amount below floor."""
    eligible = list(eligible_orders)
    if not eligible:
        return 0
    gross = sum(sum(int(item.unit_price) * int(item.quantity) for item in order.items.all()) for order in eligible)
    rate = Decimal(eligible[0].infrastructure_percent)
    variable = _money(Decimal(gross) * rate / Decimal("100"))
    return min(MONTHLY_MAXIMUM, max(MONTHLY_MINIMUM, variable))


def _proportional_fees(amount, amounts):
    """Stable integer allocation; final order absorbs rounding remainder."""
    if not amounts:
        return []
    total = sum(amounts)
    if total <= 0:
        return [0] * (len(amounts) - 1) + [int(amount)]
    portions = [int(amount) * int(v) // total for v in amounts[:-1]]
    return portions + [int(amount) - sum(portions)]


def infrastructure_allocations(orders):
    """Read-only {order id: share}, using all eligible orders of touched months.

    Can be called for one order, for a daily report, or for any partial period;
    month boundaries are always fetched independently to avoid charging the
    monthly floor repeatedly for a filtered date range.
    """
    orders = list(orders)
    eligible = [o for o in orders if Decimal(o.infrastructure_percent) > 0]
    if not eligible:
        return {}
    months = {jalali_month_bounds(o.day.date) for o in eligible}
    grouped = defaultdict(list)
    for first, last in sorted(months):
        members = list(
            TapsiOrder.objects.filter(
                day__date__gte=first, day__date__lte=last,
                infrastructure_percent__gt=0,
            ).select_related("day").prefetch_related("items").order_by("id")
        )
        if not members:
            continue
        grosses = [
            sum(int(item.unit_price) * int(item.quantity) for item in member.items.all())
            for member in members
        ]
        month_fee = infrastructure_month_total(members)
        for order, fee in zip(members, _proportional_fees(month_fee, grosses)):
            grouped[order.id].append(fee)
    return {key: sum(value) for key, value in grouped.items()}
