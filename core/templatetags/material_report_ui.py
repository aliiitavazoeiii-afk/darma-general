from django import template


register = template.Library()


@register.filter
def dict_get(value, key):
    """Presentation-only dictionary lookup for material report template data."""
    if not isinstance(value, dict):
        return {}
    return value.get(key, {}) or {}
