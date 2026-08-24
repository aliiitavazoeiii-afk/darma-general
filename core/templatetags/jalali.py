from decimal import Decimal, InvalidOperation

from django import template

from core.dateutils import format_jalali

register = template.Library()


LEGACY_MATERIAL_COLORS = [
    ("black", "مشکی"),
    ("white", "سفید"),
    ("navy", "سرمه‌ای"),
    ("pink", "صورتی"),
    ("cream", "کرم"),
    ("red", "قرمز"),
    ("yellow", "زرد"),
    ("gray", "طوسی"),
    ("stripe", "راه راه"),
]


def _norm(value):
    return (value or "").replace("ي", "ی").replace("ك", "ک").replace("‌", "").replace(" ", "").strip().lower()


@register.filter(name="jalali")
def jalali(value):
    return format_jalali(value)


@register.filter(name="groupnum")
def groupnum(value):
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        return value
    sign = "-" if number < 0 else ""
    s = str(abs(number))
    parts = []
    while s:
        parts.append(s[-3:])
        s = s[:-3]
    return sign + "٬".join(reversed(parts))


@register.filter(name="qtynum")
def qtynum(value):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return value
    text = format(number, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


@register.filter(name="absnum")
def absnum(value):
    try:
        return abs(int(value or 0))
    except (TypeError, ValueError):
        return value


@register.filter(name="pct1")
def pct1(value):
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return value


@register.filter(name="ratio_pct")
def ratio_pct(value, denominator):
    try:
        den = float(denominator)
        if den == 0:
            return 0
        return float(value) * 100 / den
    except (TypeError, ValueError, ZeroDivisionError):
        return 0


@register.simple_tag
def material_color_choices():
    """Legacy report colors plus every active color/model defined in settings."""
    from core.models import Color

    choices = list(LEGACY_MATERIAL_COLORS)
    seen = {_norm(label) for _, label in choices}
    for color in Color.objects.filter(active=True).order_by("id"):
        normalized = _norm(color.name)
        if not normalized or normalized in seen:
            continue
        choices.append((f"color:{color.id}", color.name))
        seen.add(normalized)
    return choices
