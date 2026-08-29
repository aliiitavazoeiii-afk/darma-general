from datetime import date

import jdatetime
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .excel_views import _int
from .finance import digikala_fee_for_unit, sale_line_metrics
from .models import SaleLine

TARGET_BRANDS = ("دارما", "تکوین")


def _current_month_range():
    today_j = jdatetime.date.fromgregorian(date=date.today())
    start = jdatetime.date(today_j.year, today_j.month, 1).togregorian()
    if today_j.month == 12:
        end = jdatetime.date(today_j.year + 1, 1, 1).togregorian()
    else:
        end = jdatetime.date(today_j.year, today_j.month + 1, 1).togregorian()
    return start, end, f"{today_j.year}/{today_j.month:02d}"


def _brand_current_metrics(brand_name):
    start, end, month_label = _current_month_range()
    rows = SaleLine.objects.filter(
        day__date__gte=start,
        day__date__lt=end,
        quantity__gt=0,
        product_size__product__brand__name=brand_name,
    ).select_related("day", "product_size__product", "product_size__size", "snapshot")
    gross = fee = cogs = profit = packs = shorts = 0
    for line in rows:
        m = sale_line_metrics(line)
        gross += int(m["gross"])
        fee += int(m["digikala_fee"])
        cogs += int(m["cogs"])
        profit += int(m["profit"])
        packs += int(m["packs"])
        shorts += int(m["shorts"])
    return {
        "brand": brand_name,
        "month": month_label,
        "gross": gross,
        "fee": fee,
        "cogs": cogs,
        "profit": profit,
        "packs": packs,
        "shorts": shorts,
        "profit_on_cost": (profit * 100 / cogs) if cogs else None,
        "profit_on_sale": (profit * 100 / gross) if gross else None,
    }


def _solve_sale_price(cost, target_profit_on_cost):
    cost = max(0, int(cost or 0))
    if cost <= 0:
        return 0
    target_profit = cost * float(target_profit_on_cost) / 100.0

    def achieved(price):
        return int(price) - int(digikala_fee_for_unit(int(price))) - cost

    lo = 0
    hi = max(100000, cost * 2)
    while achieved(hi) < target_profit:
        hi *= 2
        if hi > 100_000_000_000:
            raise ValueError("قیمت مناسب در محدوده محاسبات پیدا نشد.")

    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if achieved(mid) >= target_profit:
            hi = mid
        else:
            lo = mid
    return hi


def _rounded_up(value, step=1000):
    value = int(value or 0)
    return ((value + step - 1) // step) * step if value > 0 else 0


@login_required
def calculator(request):
    metrics = [_brand_current_metrics(name) for name in TARGET_BRANDS]
    return render(request, "core/calculator_v37.html", {
        "brand_metrics": metrics,
    })


@login_required
def calculator_quote(request):
    sale_price = _int(request.GET.get("sale_price"))
    cost = _int(request.GET.get("cost"))
    fee = digikala_fee_for_unit(sale_price) if sale_price > 0 else 0
    profit = sale_price - fee - cost
    return render(request, "core/_calculator_result.html", {
        "sale_price": sale_price,
        "cost": cost,
        "fee": fee,
        "profit": profit,
        "profit_on_sale": (profit * 100 / sale_price) if sale_price else 0,
        "profit_on_cost": (profit * 100 / cost) if cost else 0,
    })


@login_required
def calculator_target_quote(request):
    brand_name = (request.GET.get("brand") or "").strip()
    cost = _int(request.GET.get("new_cost"))
    if brand_name not in TARGET_BRANDS:
        return render(request, "core/_calculator_target_result_v37.html", {"error": "برند را انتخاب کن."})
    if cost <= 0:
        return render(request, "core/_calculator_target_result_v37.html", {"error": "قیمت تمام‌شده جدید را وارد کن."})

    current = _brand_current_metrics(brand_name)
    ratio = current["profit_on_cost"]
    if ratio is None:
        return render(request, "core/_calculator_target_result_v37.html", {
            "error": f"برای {brand_name} در ماه جاری فروش دارای بهای تمام‌شده پیدا نشد؛ مبنای درصد سود نداریم."
        })

    exact_price = _solve_sale_price(cost, ratio)
    suggested_price = _rounded_up(exact_price, 1000)
    fee = int(digikala_fee_for_unit(suggested_price))
    profit = suggested_price - fee - cost
    return render(request, "core/_calculator_target_result_v37.html", {
        "brand": brand_name,
        "month": current["month"],
        "current_profit_on_cost": ratio,
        "current_profit_on_sale": current["profit_on_sale"] or 0,
        "current_profit": current["profit"],
        "current_cogs": current["cogs"],
        "new_cost": cost,
        "exact_price": exact_price,
        "suggested_price": suggested_price,
        "fee": fee,
        "profit": profit,
        "profit_on_cost": (profit * 100 / cost) if cost else 0,
        "profit_on_sale": (profit * 100 / suggested_price) if suggested_price else 0,
    })
