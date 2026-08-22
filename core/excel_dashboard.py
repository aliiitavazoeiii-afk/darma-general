from collections import defaultdict
from datetime import date, timedelta

import jdatetime
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render

from .dateutils import format_jalali
from .finance import sale_line_metrics
from .models import (
    ExcelManualSetting,
    MaterialReportBlock,
    SaleDay,
    SaleLine,
    StockBalance,
    StockLocation,
    StockThreshold,
    TakvinPurchase,
)

EXCEL_TAKVIN_PREFIX = "[excel-web]"


def _empty_metrics():
    return {
        "gross": 0,
        "profit": 0,
        "shorts": 0,
        "digikala_fee": 0,
        "packs": 0,
        "cogs": 0,
        "margin": 0,
    }


def _add_metrics(target, source):
    for key in ["gross", "profit", "shorts", "digikala_fee", "packs", "cogs"]:
        target[key] += source[key]


def _finish_metrics(values):
    values["margin"] = values["profit"] * 100 / values["gross"] if values["gross"] else 0
    return values


@login_required
def dashboard(request):
    today = date.today()
    today_metrics = _empty_metrics()
    today_day = SaleDay.objects.filter(date=today).first()
    if today_day:
        for line in today_day.lines.filter(quantity__gt=0).select_related(
            "product_size__product", "product_size__size"
        ):
            _add_metrics(today_metrics, sale_line_metrics(line))
    _finish_metrics(today_metrics)

    tj = jdatetime.date.fromgregorian(date=today)
    month_start = jdatetime.date(tj.year, tj.month, 1).togregorian()
    month_metrics = _empty_metrics()
    month_lines = SaleLine.objects.filter(
        day__date__gte=month_start, day__date__lte=today, quantity__gt=0
    ).select_related("day", "product_size__product", "product_size__size")
    for line in month_lines:
        _add_metrics(month_metrics, sale_line_metrics(line))
    _finish_metrics(month_metrics)

    # 14-day chart, including days with zero sales.
    chart_start = today - timedelta(days=13)
    daily = defaultdict(lambda: {"gross": 0, "profit": 0})
    chart_lines = SaleLine.objects.filter(
        day__date__gte=chart_start, day__date__lte=today, quantity__gt=0
    ).select_related("day", "product_size__product", "product_size__size")
    for line in chart_lines:
        metrics = sale_line_metrics(line)
        daily[line.day.date]["gross"] += metrics["gross"]
        daily[line.day.date]["profit"] += metrics["profit"]

    chart_labels, chart_sales, chart_profit = [], [], []
    for offset in range(14):
        current = chart_start + timedelta(days=offset)
        jlabel = format_jalali(current)
        chart_labels.append(jlabel[5:] if len(jlabel) >= 10 else jlabel)
        chart_sales.append(daily[current]["gross"])
        chart_profit.append(daily[current]["profit"])

    # Operational alerts only; no automatic accounting is performed here.
    alerts = []
    if not today_day or not today_day.lines.filter(quantity__gt=0).exists():
        alerts.append({
            "level": "orange",
            "title": "صورت فروش امروز ثبت نشده",
            "detail": "برای امروز هنوز فروش نهایی وجود ندارد.",
            "url": "/sales/",
        })

    for threshold in StockThreshold.objects.select_related("brand", "size", "color"):
        if threshold.brand.name == "تکوین" and threshold.size.name in ("3XL", "4XL"):
            continue
        balances = StockBalance.objects.filter(
            brand=threshold.brand, size=threshold.size, color=threshold.color
        )
        home = balances.filter(location__key=StockLocation.HOME).aggregate(v=Sum("qty"))["v"] or 0
        total = balances.aggregate(v=Sum("qty"))["v"] or 0
        khorshid = balances.filter(location__key=StockLocation.KHORSHID).aggregate(v=Sum("qty"))["v"] or 0

        if threshold.total_min and total <= threshold.total_min:
            if threshold.brand.name == "تکوین":
                alerts.append({
                    "level": "orange",
                    "title": f"خرید تکوین: {threshold.color.name} / {threshold.size.name}",
                    "detail": f"موجودی کل {total}؛ حداقل تعیین‌شده {threshold.total_min}.",
                    "url": "/takvin/",
                })
            else:
                alerts.append({
                    "level": "red",
                    "title": f"نیاز به تولید: {threshold.color.name} / {threshold.size.name}",
                    "detail": f"موجودی کل {total}؛ حداقل تعیین‌شده {threshold.total_min}.",
                    "url": "/inventory/",
                })
        elif (
            threshold.brand.name == "دارما"
            and threshold.home_min
            and home <= threshold.home_min
            and khorshid > 0
        ):
            alerts.append({
                "level": "green",
                "title": f"انتقال از خورشید: {threshold.color.name} / {threshold.size.name}",
                "detail": f"خانه {home} عدد؛ خورشید {khorshid} عدد.",
                "url": "/inventory/",
            })
        if len(alerts) >= 10:
            break

    takvin_setting = ExcelManualSetting.objects.filter(key="takvin_debt").first()
    if takvin_setting and takvin_setting.value:
        alerts.append({
            "level": "orange",
            "title": "بدهی تکوین در گزارش جامع ثبت شده",
            "detail": f"مبلغ دستی فعلی: {takvin_setting.value:,} تومان",
            "url": "/report/",
        })

    purchase_month_total = TakvinPurchase.objects.filter(
        date__gte=month_start,
        date__lte=today,
        note__startswith=EXCEL_TAKVIN_PREFIX,
    ).aggregate(v=Sum("total_cost"))["v"] or 0

    return render(
        request,
        "core/dashboard_excel.html",
        {
            "today_metrics": today_metrics,
            "month_metrics": month_metrics,
            "today_j": format_jalali(today),
            "material_blocks": MaterialReportBlock.objects.count(),
            "chart_labels": chart_labels,
            "chart_sales": chart_sales,
            "chart_profit": chart_profit,
            "alerts": alerts[:10],
            "purchase_month_total": purchase_month_total,
        },
    )
