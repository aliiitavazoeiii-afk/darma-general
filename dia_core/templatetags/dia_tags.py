from django import template

register = template.Library()


@register.filter
def groupnum(value):
    try:
        return f"{int(value or 0):,}".replace(",", "٬")
    except Exception:
        return value


@register.filter
def pct1(value):
    try:
        return f"{float(value or 0):.1f}"
    except Exception:
        return "0.0"


@register.filter
def get_item(mapping, key):
    try:
        return mapping.get(key)
    except Exception:
        return None
