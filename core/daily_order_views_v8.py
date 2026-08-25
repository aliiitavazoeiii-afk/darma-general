from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from .daily_order_import_v8 import DailyOrderImportError, apply_delivery_report
from .finance_excel_v9 import sync_sale_receivable
from .models import SaleDay


@login_required
@require_POST
@transaction.atomic
def import_daily_orders(request, day_id):
    day = get_object_or_404(SaleDay, id=day_id)
    uploaded = request.FILES.get("orders_file")
    if uploaded is None:
        messages.error(request, "فایل اکسل سفارش روزانه را انتخاب کن.")
        return redirect("sale_brand", day_id=day.id)

    filename = uploaded.name or "orders.xlsx"
    if not filename.lower().endswith(".xlsx"):
        messages.error(request, "فقط فایل XLSX دیجی‌کالا قابل قبول است.")
        return redirect("sale_brand", day_id=day.id)

    try:
        data = uploaded.read()
        result = apply_delivery_report(day, data, filename)

        # Importer v8 still clears legacy manual-finance entries internally.
        # Finance v9 immediately rebuilds exactly one receivable entry per current
        # sale line, so repeated uploads are idempotent for both stock and finance.
        receivable_added = 0
        for line in day.lines.select_related(
            "day", "product_size__product", "product_size__size"
        ).all():
            receivable_added += int(sync_sale_receivable(line) or 0)
        result["digikala_receivable_added"] = receivable_added
    except DailyOrderImportError as exc:
        for line in str(exc).splitlines():
            if line.strip():
                messages.error(request, line.strip())
        return redirect("sale_brand", day_id=day.id)
    except Exception as exc:
        messages.error(request, f"ورود فایل انجام نشد: {exc}")
        return redirect("sale_brand", day_id=day.id)

    receivable_text = f"{result['digikala_receivable_added']:,}".replace(",", "٬")
    messages.success(
        request,
        f"فایل {result['filename']} ثبت شد: {result['grouped_lines']} ردیف تجمیعی، "
        f"{result['total_quantity']} کالا. طلب خالص دیجی‌کالا برای این روز: "
        f"{receivable_text} تومان.",
    )
    if result.get("shortage_count"):
        messages.warning(
            request,
            f"{result['shortage_count']} کمبود موجودی ایجاد شد؛ از ویرایش روز می‌توانی جایگزینی رنگ را مشخص کنی.",
        )
    return redirect("daily_report", day_id=day.id)
