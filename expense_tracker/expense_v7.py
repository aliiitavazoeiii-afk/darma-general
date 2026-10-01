from collections import OrderedDict
from datetime import date

import jdatetime
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.dateutils import format_jalali
from core.payment_source_v63 import SOURCE_MELAT, SOURCE_MOFID, SOURCE_LABELS

from . import views as base_views
from .models import DailyExpense, ExpenseCategory
from .services import create_expense, delete_expense, update_expense


PERSIAN_MONTH_NAMES = (
    "فروردین",
    "اردیبهشت",
    "خرداد",
    "تیر",
    "مرداد",
    "شهریور",
    "مهر",
    "آبان",
    "آذر",
    "دی",
    "بهمن",
    "اسفند",
)
PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
PAYMENT_SOURCES = (
    (SOURCE_MELAT, SOURCE_LABELS[SOURCE_MELAT]),
    (SOURCE_MOFID, SOURCE_LABELS[SOURCE_MOFID]),
)


def _persian_number(value):
    return str(value).translate(PERSIAN_DIGITS)


def _jalali_month_parts(gregorian_date):
    j = jdatetime.date.fromgregorian(date=gregorian_date)
    return j.year, j.month


def _jalali_month_label(year, month):
    return f"{PERSIAN_MONTH_NAMES[month - 1]} {_persian_number(year)}"


def _current_jalali_month_range(today):
    current = jdatetime.date.fromgregorian(date=today)
    start = jdatetime.date(current.year, current.month, 1)
    if current.month == 12:
        next_month = jdatetime.date(current.year + 1, 1, 1)
    else:
        next_month = jdatetime.date(current.year, current.month + 1, 1)
    return start.togregorian(), next_month.togregorian(), current


def _filtered_expenses(request):
    qs = DailyExpense.objects.select_related("category")
    category_id = str(request.GET.get("category") or "").strip()
    if category_id.isdigit():
        qs = qs.filter(category_id=int(category_id))

    query = str(request.GET.get("q") or "").strip()
    if query:
        qs = qs.filter(Q(title__icontains=query) | Q(note__icontains=query))

    return qs, category_id, query


def _historical_month_groups(rows, today):
    grouped = OrderedDict()
    for expense in rows:
        year, month = _jalali_month_parts(expense.date)
        key = (year, month)
        if key not in grouped:
            grouped[key] = {
                "year": year,
                "month": month,
                "label": _jalali_month_label(year, month),
                "total": 0,
                "count": 0,
                "expenses": [],
            }
        group = grouped[key]
        group["total"] += int(expense.amount or 0)
        group["count"] += 1
        group["expenses"].append(expense)

    result = []
    for group in grouped.values():
        group["day_groups"] = base_views._group_expenses_by_day(
            group["expenses"],
            today=today,
        )
        result.append(group)
    return result


def build_transaction_context(request, *, today=None):
    today = today or date.today()
    month_start, month_next, current_j = _current_jalali_month_range(today)
    qs, category_id, query = _filtered_expenses(request)

    current_qs = qs.filter(date__gte=month_start, date__lt=month_next)
    current_total = int(current_qs.aggregate(v=Sum("amount"))["v"] or 0)
    current_rows = list(current_qs.order_by("-date", "-created_at", "-id"))
    current_day_groups = base_views._group_expenses_by_day(current_rows, today=today)

    historical_rows = list(
        qs.filter(date__lt=month_start).order_by("-date", "-created_at", "-id")
    )
    historical_months = _historical_month_groups(historical_rows, today)

    return {
        "current_day_groups": current_day_groups,
        "historical_months": historical_months,
        "categories": ExpenseCategory.objects.all(),
        "selected_category": category_id,
        "query": query,
        "current_total": current_total,
        "current_month_label": _jalali_month_label(current_j.year, current_j.month),
        "today_j": format_jalali(today),
    }


@login_required
def expense_list(request):
    return render(
        request,
        "expense_tracker/expenses.html",
        build_transaction_context(request),
    )


@login_required
@require_POST
def expense_add(request):
    wants_json = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    try:
        category = get_object_or_404(
            ExpenseCategory,
            id=int(request.POST.get("category") or 0),
            active=True,
        )
        payment_source = request.POST.get("payment_source") or SOURCE_MELAT
        expense = create_expense(
            expense_date=base_views._jalali_date(request.POST.get("date")),
            amount=base_views._money(request.POST.get("amount")),
            category=category,
            payment_source=payment_source,
            title=request.POST.get("title"),
            note=request.POST.get("note"),
        )
        source_label = expense.get_payment_source_display()
        if wants_json:
            payload = base_views._dashboard_totals()
            payload.update(
                {
                    "ok": True,
                    "message": f"خرج از {source_label} ثبت شد؛ تاریخ برای ثبت بعدی ثابت ماند.",
                    "expense": {
                        "id": expense.id,
                        "title": expense.title or category.name,
                        "amount": int(expense.amount or 0),
                        "date": format_jalali(expense.date),
                        "category": category.name,
                        "accent": category.accent,
                        "payment_source": expense.payment_source,
                        "payment_source_label": source_label,
                    },
                }
            )
            return JsonResponse(payload)
        messages.success(
            request,
            f"هزینه ثبت شد و {expense.amount:,} تومان از موجودی {source_label} کم شد.",
        )
    except Exception as exc:
        if wants_json:
            return JsonResponse(
                {"ok": False, "message": f"هزینه ثبت نشد: {exc}"},
                status=400,
            )
        messages.error(request, f"هزینه ثبت نشد: {exc}")
    return redirect(request.POST.get("next") or "expense_tracker:dashboard")


@login_required
def expense_edit(request, expense_id):
    expense = get_object_or_404(
        DailyExpense.objects.select_related("category"),
        id=expense_id,
    )
    if request.method == "POST":
        try:
            category = get_object_or_404(
                ExpenseCategory,
                id=int(request.POST.get("category") or 0),
            )
            expense = update_expense(
                expense,
                expense_date=base_views._jalali_date(request.POST.get("date")),
                amount=base_views._money(request.POST.get("amount")),
                category=category,
                payment_source=request.POST.get("payment_source") or expense.payment_source,
                title=request.POST.get("title"),
                note=request.POST.get("note"),
            )
            messages.success(
                request,
                f"هزینه ویرایش شد و اثر آن روی حساب {expense.get_payment_source_display()} اصلاح شد.",
            )
            return redirect("expense_tracker:expense_list")
        except Exception as exc:
            messages.error(request, f"ویرایش انجام نشد: {exc}")
    return render(
        request,
        "expense_tracker/expense_edit.html",
        {
            "expense": expense,
            "categories": ExpenseCategory.objects.all(),
            "expense_j": format_jalali(expense.date),
            "payment_sources": PAYMENT_SOURCES,
        },
    )


@login_required
@require_POST
def expense_delete(request, expense_id):
    expense = get_object_or_404(DailyExpense, id=expense_id)
    try:
        amount = int(expense.amount or 0)
        source_label = expense.get_payment_source_display()
        delete_expense(expense)
        messages.success(
            request,
            f"هزینه حذف شد و {amount:,} تومان به حساب {source_label} برگشت.",
        )
    except Exception as exc:
        messages.error(request, f"حذف انجام نشد: {exc}")
    return redirect(request.POST.get("next") or "expense_tracker:expense_list")
