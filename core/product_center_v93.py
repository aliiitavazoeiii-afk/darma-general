from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from . import pricing_v60
from . import settings_rules_v17 as rules_v17
from .dateutils import format_jalali, parse_jalali_date
from .models import AppSetting, ProductCode, ProductSize, TakvinCostRule
from .sale_price_v60 import next_sale_price_rule, sale_price_for, set_sale_price_rule
from .takvin_pricing_v17 import TAKVIN_SIZES, current_takvin_costs


DARMA_PRICE_SIZES = tuple(pricing_v60.SIZE_NAMES)
TAKVIN_PRICE_SIZES = tuple(TAKVIN_SIZES)
RULE_ACTIONS = {
    "darma_cost_rule",
    "darma_delete_rule",
    "novani_cost_rule",
    "novani_delete_rule",
    "takvin_cost_rule",
    "takvin_delete_rule_set",
    "base_settings",
}


def _money(value):
    try:
        return int(
            str(value or "0")
            .replace("٬", "")
            .replace(",", "")
            .replace(" ", "")
            .strip()
        )
    except (TypeError, ValueError):
        return 0


def _tomorrow():
    return date.today() + timedelta(days=1)


def _rules_context():
    settings = list(
        AppSetting.objects.exclude(key__startswith=rules_v17.DARMA_RULE_PREFIX)
        .exclude(key__startswith=rules_v17.NOVANI_RULE_PREFIX)
        .exclude(key__startswith=rules_v17.SALE_PRICE_RULE_PREFIX)
        .exclude(key=rules_v17.LEGACY_FALLBACK_KEY)
        .order_by("id")
    )

    grouped = {}
    for rule in TakvinCostRule.objects.select_related("size").order_by(
        "-effective_from", "size__sort_order"
    ):
        key = rule.effective_from
        grouped.setdefault(
            key,
            {
                "date": rule.effective_from,
                "jalali": format_jalali(rule.effective_from),
                "prices": {},
            },
        )
        grouped[key]["prices"][rule.size.name] = int(rule.unit_cost)

    darma_history = [
        {
            "date": row["effective_from"],
            "jalali": format_jalali(row["effective_from"]),
            "unit_cost": int(row["unit_cost"]),
            "is_baseline": bool(row.get("is_baseline")),
        }
        for row in rules_v17.list_darma_cost_rules()
    ]
    novani_history = [
        {
            "date": row["effective_from"],
            "jalali": format_jalali(row["effective_from"]),
            "unit_cost": int(row["unit_cost"]),
            "is_baseline": bool(row.get("is_baseline")),
        }
        for row in rules_v17.list_novani_cost_rules()
    ]

    return {
        "settings": settings,
        "darma_current": int(rules_v17.darma_cost_for()),
        "darma_history": darma_history,
        "novani_current": int(rules_v17.novani_cost_for()),
        "novani_history": novani_history,
        "takvin_sizes": TAKVIN_PRICE_SIZES,
        "takvin_current": current_takvin_costs(),
        "takvin_history": list(grouped.values()),
    }


def _display_price(product_size):
    nxt = next_sale_price_rule(product_size)
    if nxt:
        return {
            "value": int(nxt["price"]),
            "future": True,
            "effective_from": nxt["effective_from"],
            "effective_j": format_jalali(nxt["effective_from"]),
            "current": int(sale_price_for(product_size, date.today())),
        }
    return {
        "value": int(sale_price_for(product_size, date.today())),
        "future": False,
        "effective_from": None,
        "effective_j": "",
        "current": int(sale_price_for(product_size, date.today())),
    }


def _product_pricing_rows(brand_name, size_names):
    products = list(
        ProductCode.objects.filter(brand__name=brand_name, active=True)
        .select_related("brand")
        .prefetch_related("sizes__size")
        .order_by("code")
    )
    rows = []
    for product in products:
        by_name = {
            ps.size.name: ps
            for ps in product.sizes.all()
            if ps.active and ps.size.name in size_names
        }
        if not by_name:
            continue
        future_dates = []
        cells = []
        for size_name in size_names:
            ps = by_name.get(size_name)
            if ps is None:
                cells.append({"size": size_name, "active": False})
                continue
            info = _display_price(ps)
            if info["effective_from"]:
                future_dates.append(info["effective_from"])
            cells.append(
                {
                    "size": size_name,
                    "active": True,
                    "ps_id": ps.id,
                    **info,
                }
            )
        rows.append(
            {
                "product": product,
                "cells": cells,
                "effective_j": format_jalali(
                    min(future_dates) if future_dates else _tomorrow()
                ),
            }
        )
    return rows


def _takvin_bulk_row():
    cells = []
    for size_name in TAKVIN_PRICE_SIZES:
        product_sizes = list(
            ProductSize.objects.filter(
                product__brand__name="تکوین",
                product__active=True,
                active=True,
                size__name=size_name,
            )
            .select_related("product__brand", "size")
            .order_by("product__code", "id")
        )
        values = []
        for ps in product_sizes:
            values.append(_display_price(ps)["value"])
        unique = sorted(set(values))
        cells.append(
            {
                "size": size_name,
                "value": unique[0] if len(unique) == 1 else "",
                "mixed": len(unique) > 1,
                "count": len(product_sizes),
            }
        )
    return {
        "cells": cells,
        "effective_j": format_jalali(_tomorrow()),
        "product_count": ProductCode.objects.filter(
            brand__name="تکوین", active=True, sizes__active=True
        ).distinct().count(),
    }


def _schedule_product_prices(product, effective_from, post):
    if product.brand.name not in {"دارما", "تکوین"}:
        raise ValueError("قیمت‌گذاری تاریخ‌دار فقط برای دارما و تکوین فعال است.")
    if effective_from < date.today():
        raise ValueError("تاریخ شروع قیمت فروش نمی‌تواند قبل از امروز باشد.")

    allowed_sizes = DARMA_PRICE_SIZES if product.brand.name == "دارما" else TAKVIN_PRICE_SIZES
    product_sizes = list(
        ProductSize.objects.filter(
            product=product,
            active=True,
            size__name__in=allowed_sizes,
        ).select_related("product__brand", "size")
    )
    if not product_sizes:
        raise ValueError("این کد هیچ سایز فعال قابل قیمت‌گذاری ندارد.")

    prices = {}
    for ps in product_sizes:
        price = _money(post.get(f"price_{ps.id}"))
        if price <= 0:
            raise ValueError(f"قیمت {product.code} / {ps.size.name} باید بیشتر از صفر باشد.")
        prices[ps.id] = price

    with transaction.atomic():
        for ps in product_sizes:
            set_sale_price_rule(ps, effective_from, prices[ps.id])
    return len(product_sizes)


def _schedule_takvin_bulk(effective_from, post):
    if effective_from < date.today():
        raise ValueError("تاریخ شروع قیمت فروش نمی‌تواند قبل از امروز باشد.")

    prices = {}
    for size_name in TAKVIN_PRICE_SIZES:
        price = _money(post.get(f"price_{size_name}"))
        if price <= 0:
            raise ValueError(f"قیمت فروش تکوین سایز {size_name} باید بیشتر از صفر باشد.")
        prices[size_name] = price

    product_sizes = list(
        ProductSize.objects.filter(
            product__brand__name="تکوین",
            product__active=True,
            active=True,
            size__name__in=TAKVIN_PRICE_SIZES,
        ).select_related("product__brand", "product", "size")
    )
    if not product_sizes:
        raise ValueError("هیچ کد فعال تکوین برای قیمت‌گذاری پیدا نشد.")

    with transaction.atomic():
        for ps in product_sizes:
            set_sale_price_rule(ps, effective_from, prices[ps.size.name])

    return {
        "rows": len(product_sizes),
        "products": len({ps.product_id for ps in product_sizes}),
    }


def _handle_pricing_post(request):
    action = request.POST.get("action") or ""
    if action == "bulk_darma_prices":
        pack_qty = pricing_v60._int(request.POST.get("pack_qty"))
        effective_from = parse_jalali_date(
            request.POST.get("effective_from") or format_jalali(_tomorrow())
        )
        prices = {
            size_name: pricing_v60._int(request.POST.get(f"price_{size_name}"))
            for size_name in DARMA_PRICE_SIZES
        }
        with transaction.atomic():
            result = pricing_v60._schedule_group_prices(pack_qty, effective_from, prices)
        messages.success(
            request,
            f"قیمت پک {pack_qty} تایی برای {result['products']} کد دارما از تاریخ "
            f"{format_jalali(effective_from)} زمان‌بندی شد. قیمت روزهای قبل تغییر نمی‌کند.",
        )
        return "darma"

    if action == "bulk_takvin_prices":
        effective_from = parse_jalali_date(
            request.POST.get("effective_from") or format_jalali(_tomorrow())
        )
        result = _schedule_takvin_bulk(effective_from, request.POST)
        messages.success(
            request,
            f"قیمت فروش {result['products']} کد فعال تکوین از تاریخ "
            f"{format_jalali(effective_from)} به‌صورت گروهی زمان‌بندی شد.",
        )
        return "takvin"

    if action == "product_sale_prices":
        product = get_object_or_404(
            ProductCode.objects.select_related("brand"),
            id=request.POST.get("product_id"),
            active=True,
        )
        effective_from = parse_jalali_date(
            request.POST.get("effective_from") or format_jalali(_tomorrow())
        )
        count = _schedule_product_prices(product, effective_from, request.POST)
        messages.success(
            request,
            f"قیمت فروش {product.brand.name} / {product.code} برای {count} سایز از تاریخ "
            f"{format_jalali(effective_from)} زمان‌بندی شد.",
        )
        return "darma" if product.brand.name == "دارما" else "takvin"

    raise ValueError("عملیات قیمت‌گذاری معتبر نیست.")


@login_required
def settings_products(request):
    section = (request.GET.get("section") or "").strip().lower()
    if section not in {"rules", "pricing", "colors"}:
        section = ""
    pricing_brand = (request.GET.get("brand") or "").strip().lower()
    if pricing_brand not in {"darma", "takvin"}:
        pricing_brand = ""

    if request.method == "POST":
        action = request.POST.get("action") or ""
        if action in RULE_ACTIONS:
            return rules_v17.settings_rules(request)
        try:
            pricing_brand = _handle_pricing_post(request)
        except Exception as exc:
            messages.error(request, str(exc))
        suffix = f"?section=pricing&brand={pricing_brand}" if pricing_brand else "?section=pricing"
        return redirect(f"/settings/products/{suffix}")

    rules_context = _rules_context()
    products = list(
        ProductCode.objects.select_related("brand")
        .prefetch_related("composition__color", "sizes__size")
        .all()
        .order_by("brand__name", "code")
    )

    context = {
        **rules_context,
        "section": section,
        "pricing_brand": pricing_brand,
        "products": products,
        "active_product_count": sum(1 for product in products if product.active),
        "darma_product_count": ProductCode.objects.filter(brand__name="دارما", active=True).count(),
        "takvin_product_count": ProductCode.objects.filter(brand__name="تکوین", active=True).count(),
        "pricing_sizes_darma": DARMA_PRICE_SIZES,
        "pricing_sizes_takvin": TAKVIN_PRICE_SIZES,
        "bulk_effective_j": format_jalali(_tomorrow()),
        "darma_bulk_rows": pricing_v60._pricing_rows(),
        "darma_price_rows": _product_pricing_rows("دارما", DARMA_PRICE_SIZES),
        "takvin_bulk": _takvin_bulk_row(),
        "takvin_price_rows": _product_pricing_rows("تکوین", TAKVIN_PRICE_SIZES),
    }
    return render(request, "core/settings_products_v93.html", context)


@login_required
def settings_rules_compat(request):
    """Old bookmark compatibility: POST keeps old mutation semantics; GET opens V93 rules."""
    if request.method == "POST":
        return rules_v17.settings_rules(request)
    return redirect("/settings/products/?section=rules")
