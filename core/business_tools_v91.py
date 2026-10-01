from datetime import date

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render

from . import business_receipts_v64 as receipts_v64
from . import business_tools_v21 as v21
from . import business_tools_v60 as v60
from . import business_tools_v62 as v62
from .dateutils import format_jalali, parse_jalali_date
from .material_flow import COLOR_LABELS
from .models import BusinessPayment, DigikalaSettlement
from .payment_source_v63 import SOURCE_CHOICES
from .finance_overview_v104 import finance_kpis


RECEIPT_FILTER_ALL = "all"


def _receipt_filter_data(request):
    raw_from = (request.GET.get("receipt_from") or "").strip()
    raw_to = (request.GET.get("receipt_to") or "").strip()
    source = (request.GET.get("receipt_source") or RECEIPT_FILTER_ALL).strip()
    allowed_sources = {key for key, _label in receipts_v64.SOURCE_CHOICES}
    active = bool(raw_from or raw_to or source != RECEIPT_FILTER_ALL)
    error = ""
    start_date = None
    end_date = None

    try:
        if raw_from:
            start_date = parse_jalali_date(raw_from)
        if raw_to:
            end_date = parse_jalali_date(raw_to)
        if start_date and end_date and start_date > end_date:
            raise ValueError("تاریخ شروع نمی‌تواند بعد از تاریخ پایان باشد.")
        if source != RECEIPT_FILTER_ALL and source not in allowed_sources:
            raise ValueError("منبع دریافتی فیلتر معتبر نیست.")
    except Exception as exc:
        error = str(exc)

    if error:
        rows = []
        total = 0
        count = 0
    else:
        qs = DigikalaSettlement.objects.all().order_by("-date", "-id")
        if start_date:
            qs = qs.filter(date__gte=start_date)
        if end_date:
            qs = qs.filter(date__lte=end_date)
        if source != RECEIPT_FILTER_ALL:
            qs = qs.filter(source=source)

        total = int(qs.aggregate(v=Sum("amount"))["v"] or 0)
        rows = list(qs)
        count = len(rows)
        for row in rows:
            row.source = receipts_v64.normalize_source(
                getattr(row, "source", receipts_v64.SOURCE_DIGIKALA)
            )
            row.source_label = receipts_v64.SOURCE_LABELS[row.source]

    return {
        "rows": rows,
        "total": total,
        "count": count,
        "active": active,
        "error": error,
        "raw_from": raw_from,
        "raw_to": raw_to,
        "source": source,
        "sources": (
            (RECEIPT_FILTER_ALL, "همه دریافتی‌ها"),
            *receipts_v64.SOURCE_CHOICES,
        ),
    }


@login_required
def payments(request):
    """V91 read-only receipts filtering layered over the V62/V64 finance flow."""
    section = (request.GET.get("section") or "").strip().lower()
    if section not in {"payments", "receipts"}:
        section = ""

    month_start, month_next, month_label = v21._current_jalali_month_range()
    payment_month_total = int(
        BusinessPayment.objects.filter(
            date__gte=month_start,
            date__lt=month_next,
        ).aggregate(v=Sum("amount"))["v"] or 0
    )
    receipt_month_total = int(
        DigikalaSettlement.objects.filter(
            date__gte=month_start,
            date__lt=month_next,
        ).aggregate(v=Sum("amount"))["v"] or 0
    )

    payment_rows = v62._payment_rows() if section == "payments" else []
    elastic_multi_payloads = {
        str(row.id): row.purchase_data
        for row in payment_rows
        if (row.purchase_data or {}).get("k") == v60.MULTI_KIND
    }
    payment_source_payloads = {
        str(row.id): v62._payment_source(row)
        for row in payment_rows
    }

    receipt_filter = _receipt_filter_data(request) if section == "receipts" else {
        "rows": [],
        "total": 0,
        "count": 0,
        "active": False,
        "error": "",
        "raw_from": "",
        "raw_to": "",
        "source": RECEIPT_FILTER_ALL,
        "sources": ((RECEIPT_FILTER_ALL, "همه دریافتی‌ها"), *receipts_v64.SOURCE_CHOICES),
    }

    return render(
        request,
        "core/payments_v91.html",
        {
            "section": section,
            "payment_rows": payment_rows,
            "elastic_multi_payloads": elastic_multi_payloads,
            "payment_source_payloads": payment_source_payloads,
            "receipt_rows": receipt_filter["rows"],
            "receipt_filtered_total": receipt_filter["total"],
            "receipt_filtered_count": receipt_filter["count"],
            "receipt_filter_active": receipt_filter["active"],
            "receipt_filter_error": receipt_filter["error"],
            "receipt_filter_from": receipt_filter["raw_from"],
            "receipt_filter_to": receipt_filter["raw_to"],
            "receipt_filter_source": receipt_filter["source"],
            "receipt_filter_sources": receipt_filter["sources"],
            "today_j": format_jalali(date.today()),
            **finance_kpis(),
            "receipt_source_choices": receipts_v64.SOURCE_CHOICES,
            "payees": v62.PAYEE_CHOICES,
            "payment_source_choices": SOURCE_CHOICES,
            "material_colors": list(COLOR_LABELS.items()),
            "payment_month_total": payment_month_total,
            "receipt_month_total": receipt_month_total,
            "month_label": month_label,
        },
    )
