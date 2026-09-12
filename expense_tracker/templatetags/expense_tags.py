from django import template

register = template.Library()


@register.filter
def daily_average(month_total, jalali_date):
    try:
        total = int(month_total or 0)
        day = int(str(jalali_date or "").split("/")[-1])
        day = max(1, day)
        return (total + day // 2) // day
    except (TypeError, ValueError):
        return 0
