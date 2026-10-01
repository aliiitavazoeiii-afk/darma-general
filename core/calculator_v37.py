from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .darma_cost_v55 import darma_cost_for
from .excel_views import _int
from .finance import digikala_fee_for_unit
from .models import ProductSize
from .sale_price_v60 import sale_price_for
from .takvin_pricing_v17 import takvin_cost_for


TARGET_BRANDS = ("دارما", "تکوین")


def _percent(value):
    text = str(value or "").strip()
    if not text:
        return None
    text = (
        text.replace("٪", "")
        .replace("٫", ".")
        .replace(",", ".")
        .replace(" ", "")
    )
    try:
        value = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    if value < 0:
        return None
    return value


def _solve_sale_price(cost, target_profit_on_cost):
    """Minimum whole-toman sale price that reaches the requested net markup.

    Target percentage means:
        net profit / finished cost * 100

    Digikala fee is always calculated by the canonical live fee engine.
    """
    cost = max(0, int(cost or 0))
    if cost <= 0:
        return 0
    ratio = Decimal(target_profit_on_cost)
    target_profit = Decimal(cost) * ratio / Decimal(100)

    def achieved(price):
        return Decimal(int(price) - int(digikala_fee_for_unit(int(price), date.today())) - cost)

    lo = 0
    hi = max(100_000, cost * 2)
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
    return int(hi)


def _rounded_up(value, step=1000):
    value = int(value or 0)
    return ((value + step - 1) // step) * step if value > 0 else 0


def _profitability_rows():
    today = date.today()
    rows = list(
        ProductSize.objects.filter(
            product__brand__name__in=TARGET_BRANDS,
            product__active=True,
            active=True,
        )
        .select_related("product__brand", "product", "size")
        .order_by("product__brand__name", "product__code", "size__sort_order", "id")
    )

    sections = {brand: [] for brand in TARGET_BRANDS}
    for ps in rows:
        brand = ps.product.brand.name
        pack_qty = int(ps.product.pack_qty or 0)
        sale_price = int(sale_price_for(ps, today) or 0)

        if brand == "دارما":
            unit_cost = int(darma_cost_for(today) or 0)
        else:
            unit_cost = int(takvin_cost_for(ps.size.name, today) or 0)

        finished_cost = pack_qty * unit_cost
        fee = int(digikala_fee_for_unit(sale_price, today)) if sale_price > 0 else 0
        profit = sale_price - fee - finished_cost if sale_price > 0 else 0
        profit_on_cost = (profit * 100 / finished_cost) if finished_cost else 0
        profit_on_sale = (profit * 100 / sale_price) if sale_price else 0

        sections[brand].append({
            "ps_id": ps.id,
            "brand": brand,
            "code": ps.product.code,
            "size": ps.size.name,
            "pack_qty": pack_qty,
            "sale_price": sale_price,
            "unit_cost": unit_cost,
            "finished_cost": finished_cost,
            "fee": fee,
            "profit": profit,
            "profit_on_cost": profit_on_cost,
            "profit_on_sale": profit_on_sale,
        })

    return [
        {"brand": brand, "rows": sections[brand], "count": len(sections[brand])}
        for brand in TARGET_BRANDS
    ]


@login_required
def calculator(request):
    return render(
        request,
        "core/calculator_v37.html",
        {
            "profitability_sections": _profitability_rows(),
        },
    )


@login_required
def calculator_quote(request):
    sale_price = _int(request.GET.get("sale_price"))
    cost = _int(request.GET.get("cost"))
    if sale_price <= 0 or cost <= 0:
        return render(
            request,
            "core/_calculator_result_v104.html",
            {"error": "قیمت فروش و قیمت تمام‌شده را کامل وارد کن."},
        )

    fee = int(digikala_fee_for_unit(sale_price, date.today()))
    profit = sale_price - fee - cost
    return render(request, "core/_calculator_result_v104.html", {
        "sale_price": sale_price,
        "cost": cost,
        "fee": fee,
        "profit": profit,
        "profit_on_sale": (profit * 100 / sale_price) if sale_price else 0,
        "profit_on_cost": (profit * 100 / cost) if cost else 0,
    })


@login_required
def calculator_target_quote(request):
    cost = _int(request.GET.get("cost"))
    target_percent = _percent(request.GET.get("target_profit_percent"))
    if cost <= 0:
        return render(
            request,
            "core/_calculator_target_result_v104.html",
            {"error": "قیمت تمام‌شده کالا را وارد کن."},
        )
    if target_percent is None:
        return render(
            request,
            "core/_calculator_target_result_v104.html",
            {"error": "درصد سود هدف را به‌صورت عدد صفر یا بیشتر وارد کن."},
        )

    exact_price = _solve_sale_price(cost, target_percent)
    suggested_price = _rounded_up(exact_price, 1000)
    fee = int(digikala_fee_for_unit(suggested_price, date.today()))
    profit = suggested_price - fee - cost
    return render(request, "core/_calculator_target_result_v104.html", {
        "cost": cost,
        "target_profit_percent": float(target_percent),
        "exact_price": exact_price,
        "suggested_price": suggested_price,
        "fee": fee,
        "profit": profit,
        "profit_on_cost": (profit * 100 / cost) if cost else 0,
        "profit_on_sale": (profit * 100 / suggested_price) if suggested_price else 0,
    })
