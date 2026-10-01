from collections import OrderedDict
from datetime import date

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, render

from . import expense_v7, views as base_views
from .models import DailyExpense, ExpenseCategory


def _category_report_context(category, *, today=None):
    today = today or date.today()
    month_start, month_next, current_j = expense_v7._current_jalali_month_range(today)

    qs = DailyExpense.objects.filter(category=category).select_related("category")
    all_total = int(qs.aggregate(v=Sum("amount"))["v"] or 0)
    all_count = qs.count()
    current_month_total = int(
        qs.filter(date__gte=month_start, date__lt=month_next).aggregate(v=Sum("amount"))["v"] or 0
    )
    current_month_count = qs.filter(date__gte=month_start, date__lt=month_next).count()

    largest_expenses = list(
        qs.order_by("-amount", "-date", "-created_at", "-id")[:5]
    )

    rows = list(qs.order_by("-date", "-created_at", "-id"))
    month_map = OrderedDict()
    current_key = (current_j.year, current_j.month)
    for expense in rows:
        year, month = expense_v7._jalali_month_parts(expense.date)
        key = (year, month)
        if key not in month_map:
            month_map[key] = {
                "year": year,
                "month": month,
                "label": expense_v7._jalali_month_label(year, month),
                "total": 0,
                "count": 0,
                "expenses": [],
                "is_current": key == current_key,
            }
        group = month_map[key]
        group["total"] += int(expense.amount or 0)
        group["count"] += 1
        group["expenses"].append(expense)

    month_groups = []
    for group in month_map.values():
        group["day_groups"] = base_views._group_expenses_by_day(group["expenses"], today=today)
        month_groups.append(group)

    largest_amount = int(largest_expenses[0].amount or 0) if largest_expenses else 0
    for expense in largest_expenses:
        expense.rank_pct = round(int(expense.amount or 0) * 100 / largest_amount, 1) if largest_amount else 0

    return {
        "category": category,
        "current_month_label": expense_v7._jalali_month_label(current_j.year, current_j.month),
        "current_month_total": current_month_total,
        "current_month_count": current_month_count,
        "all_total": all_total,
        "all_count": all_count,
        "largest_expenses": largest_expenses,
        "month_groups": month_groups,
    }


@login_required
def category_report(request, category_id):
    category = get_object_or_404(ExpenseCategory, id=category_id)
    return render(
        request,
        "expense_tracker/category_report.html",
        _category_report_context(category),
    )
