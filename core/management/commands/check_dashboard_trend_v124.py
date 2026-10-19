"""Read-only diagnosis and regression for the 30 monetary sales-day trend."""
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from core.dateutils import format_jalali
from core.dia_gallery_v45 import dia_gallery_period_metrics
from core.excel_dashboard_v89 import recent_paid_sale_days
from core.finance import sale_line_metrics
from core.models import DiaGallerySale, SaleDay, SaleLine


class Command(BaseCommand):
    help = "Read-only: inspect 30 chart sale-days, zero-priced draft days and any true loss."

    def handle(self, *args, **kwargs):
        source = (Path(settings.BASE_DIR) / "templates/core/dashboard_excel_v89.html").read_text(encoding="utf-8")
        for marker in (
            'lowestProfit', 'min:lowestProfit',
            "autoSkip:true", "Number(c.raw)<0",
            'dashboard-chart-labels', 'dashboard-chart-profit',
        ):
            if marker not in source:
                raise RuntimeError(f"V124 chart axis/date/negative-profit UI regression: {marker}")
        today = date.today()
        chart_days = recent_paid_sale_days(today, 30)
        dates = [d.date for d in chart_days]
        if dates != sorted(dates) or len(dates) != len(set(dates)):
            raise RuntimeError("Chart dates not sorted/unique")
        if not chart_days:
            self.stdout.write("NO PAID SALES YET / dashboard handles empty chart")
            return
        chart_start, chart_end = dates[0], dates[-1]
        by_date = defaultdict(lambda: {"gross": 0, "profit": 0, "units": 0})
        for line in SaleLine.objects.filter(
            day__date__gte=chart_start, day__date__lte=chart_end, quantity__gt=0
        ).select_related("day", "product_size__product__brand", "product_size__size"):
            metrics = sale_line_metrics(line)
            row = by_date[line.day.date]
            row["gross"] += int(metrics["gross"] or 0)
            row["profit"] += int(metrics["profit"] or 0)
            row["units"] += int(metrics["shorts"] or 0)
        for line in dia_gallery_period_metrics(chart_start, chart_end)["rows"]:
            row = by_date[line["date"]]
            row["gross"] += int(line["gross"] or 0)
            row["profit"] += int(line["profit"] or 0)
            row["units"] += int(line["shorts"] or 0)
        for d in dates:
            m = by_date[d]
            if m["gross"] <= 0:
                raise RuntimeError(f"Phantom zero-gross date still on graph: {d}")
            status = "REAL_LOSS" if m["profit"] < 0 else "OK"
            self.stdout.write(
                f"CHART_DAY={format_jalali(d)} GROSS={m['gross']} "
                f"PROFIT={m['profit']} SHORTS={m['units']} STATUS={status}"
            )
        recent = today-timedelta(days=50)
        draft_days = set(SaleLine.objects.filter(
            day__date__gte=recent, day__date__lte=today,
            quantity__gt=0, sale_price=0,
        ).values_list("day__date", flat=True))
        dia_drafts = set(DiaGallerySale.objects.filter(
            day__date__gte=recent, day__date__lte=today,
            quantity__gt=0, unit_price=0,
        ).values_list("day__date", flat=True))
        if draft_days or dia_drafts:
            self.stdout.write("ZERO_PRICE_DRAFT_DATES=" +
                              ",".join(format_jalali(d) for d in sorted(draft_days|dia_drafts)))
        self.stdout.write(f"CHART_COUNT={len(chart_days)} POSITIVE_GROSS_DAYS_ONLY=YES")
        self.stdout.write("READ_ONLY / NO SALES, STOCK, FINANCE OR DATABASE WRITES")
        self.stdout.write(self.style.SUCCESS("SUCCESS: V124 DASHBOARD TREND CHECK PASSED"))
