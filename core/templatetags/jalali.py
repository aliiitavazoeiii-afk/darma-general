from django import template

from core.dateutils import format_jalali

register = template.Library()


@register.filter(name="jalali")
def jalali(value):
    return format_jalali(value)
