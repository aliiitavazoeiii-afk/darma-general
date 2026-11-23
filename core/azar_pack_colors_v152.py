"""V152: date-effective physical color composition for two Darma SKUs.

From 1405/09/01 (= 2026-11-22), all Darma sales of pack6 `06`
substitute one cream with one red per pack, and pack12 `p12`
substitute two gray with two red per pack.  Old recorded dates,
other brands, other SKUs, and the persistent ProductComposition rows
must remain unchanged.

This module is used both by the standard sale-inventory posting
path (including reimport) and by the historical one-time backfill.
"""
from dataclasses import dataclass
from datetime import date

from .brand_colors import norm
from .models import Color, ProductComposition

START_DATE = date(2026, 11, 22)  # 1405/09/01 inclusive
BRAND_NAME = "دارما"

# code: (exact pack quantity, old stock color, red pieces per pack)
RULES = {
    "06": (6, "کرم", 1),
    "p12": (12, "طوسی", 2),
}
RED = "قرمز"


@dataclass(frozen=True)
class EffectiveComponent:
    color: Color
    qty: int

    @property
    def color_id(self):
        return self.color.pk


def color_for_name(name):
    matches = [c for c in Color.objects.filter(active=True) if norm(c.name) == norm(name)]
    if len(matches) != 1:
        raise ValueError(f"رنگ فعال و یکتای «{name}» در جدول رنگ‌ها پیدا نشد.")
    return matches[0]


def correction_rule(line):
    product = line.product_size.product
    if (
        product.brand.name == BRAND_NAME
        and line.day.date >= START_DATE
        and product.code in RULES
    ):
        return RULES[product.code]
    return None


def effective_sale_compositions(line):
    """Read-only; returns virtual rows with the original pack quantity preserved."""
    product = line.product_size.product
    compositions = list(
        ProductComposition.objects.filter(product=product).select_related("color").order_by("pk")
    )
    rule = correction_rule(line)
    if not rule:
        return compositions

    expected_pack, source_name, replace_count = rule
    original_pack = sum(int(c.qty) for c in compositions)
    if int(product.pack_qty) != expected_pack or original_pack != expected_pack:
        raise ValueError(
            f"ترکیب کد {product.code} باید پک {expected_pack} عددی و کامل باشد؛ "
            f"پک={product.pack_qty}، جمع ترکیب={original_pack}."
        )
    source_color = color_for_name(source_name)
    red_color = color_for_name(RED)
    quantities = {c.color_id: int(c.qty) for c in compositions}
    if quantities.get(source_color.pk, 0) < replace_count:
        raise ValueError(
            f"در ترکیب اصلی کد {product.code} حداقل {replace_count} عدد «{source_name}» "
            "برای اصلاح از اول آذر وجود ندارد؛ اصلاح موجودی متوقف شد."
        )
    quantities[source_color.pk] -= replace_count
    quantities[red_color.pk] = quantities.get(red_color.pk, 0) + replace_count

    colors = {c.color_id: c.color for c in compositions}
    colors[red_color.pk] = red_color
    result = [
        EffectiveComponent(colors[color_id], qty)
        for color_id, qty in quantities.items()
        if qty > 0
    ]
    if sum(c.qty for c in result) != expected_pack:
        raise ValueError("جمع ترکیب جدید با تعداد پک برابر نیست.")
    return result
