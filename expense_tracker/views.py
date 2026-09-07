import re
from datetime import date, timedelta

import jdatetime
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from core.dateutils import format_jalali, parse_jalali_date

from .models import DailyExpense, ExpenseCategory, ReceivableEntry, ReceivablePerson
from .services import (
    create_claim,
    create_expense,
    delete_expense,
    delete_receivable_entry,
    mellat_balance,
    outstanding_for_person,
    record_repayment,
    update_expense,
)


PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
ACCENTS = ("green", "blue", "violet", "amber", "coral", "cyan")


def _money(value):
    text = str(value or "").translate(PERSIAN_DIGITS)
    text = re.sub(r"[^0-9-]", "", text)
    try:
        return int(text or 0)
    except ValueError:
        return 0


def _jalali_date(value=None):
    raw = str(value or "").strip()
    return parse_jalali_date(raw) if raw else date.today()


def _current_month_range(today=None):
    today = today or date.today()
    j = jdatetime.date.fromgregorian(date=today)
    start_j = jdatetime.date(j.year, j.month, 1)
    if j.month == 12:
        next_j = jdatetime.date(j.year + 1, 1, 1)
    else:
        next_j = jdatetime.date(j.year, j.month + 1, 1)
    return start_j.togregorian(), next_j.togregorian(), f"{j.year}/{j.month:02d}"


def _week_start(today=None):
    today = today or date.today()
    return today - timedelta(days=(today.weekday() - 5) % 7)


def _sum_expenses(qs):
    return int(qs.aggregate(v=Sum("amount"))["v"] or 0)


def _category_rows(qs):
    rows = list(
        qs.values("category__id", "category__name", "category__accent")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )
    grand = sum(int(row["total"] or 0) for row in rows)
    for row in rows:
        row["total"] = int(row["total"] or 0)
        row["pct"] = round((row["total"] * 100 / grand), 1) if grand else 0
    return rows


def _dashboard_totals(today=None):
    today = today or date.today()
    week_start = _week_start(today)
    month_start, month_next, _month_label = _current_month_range(today)
    return {
        "mellat_balance": mellat_balance(),
        "today_total": _sum_expenses(DailyExpense.objects.filter(date=today)),
        "week_total": _sum_expenses(
            DailyExpense.objects.filter(date__gte=week_start, date__lte=today)
        ),
        "month_total": _sum_expenses(
            DailyExpense.objects.filter(date__gte=month_start, date__lt=month_next)
        ),
    }


def _receivable_people():
    people = list(ReceivablePerson.objects.filter(active=True).order_by("name", "id"))
    for person in people:
        totals = {
            row["kind"]: int(row["total"] or 0)
            for row in person.entries.values("kind").annotate(total=Sum("amount"))
        }
        person.claim_total = totals.get(ReceivableEntry.CLAIM, 0)
        person.payment_total = totals.get(ReceivableEntry.PAYMENT, 0)
        person.outstanding = person.claim_total - person.payment_total
    return people


@login_required
def dashboard(request):
    today = date.today()
    week_start = _week_start(today)
    month_start, month_next, month_label = _current_month_range(today)

    active_categories = list(ExpenseCategory.objects.filter(active=True))
    today_qs = DailyExpense.objects.filter(date=today)
    week_qs = DailyExpense.objects.filter(date__gte=week_start, date__lte=today)
    month_qs = DailyExpense.objects.filter(date__gte=month_start, date__lt=month_next)

    seven_start = today - timedelta(days=6)
    seven_map = {
        row["date"]: int(row["total"] or 0)
        for row in (
            DailyExpense.objects.filter(date__gte=seven_start, date__lte=today)
            .values("date")
            .annotate(total=Sum("amount"))
        )
    }
    day_rows = []
    max_day = max(seven_map.values(), default=0)
    for offset in range(7):
        current = seven_start + timedelta(days=offset)
        amount = seven_map.get(current, 0)
        day_rows.append(
            {
                "date": current,
                "jalali": format_jalali(current),
                "amount": amount,
                "pct": round(amount * 100 / max_day, 1) if max_day else 0,
            }
        )

    people = _receivable_people()
    total_receivable = sum(max(0, int(p.outstanding or 0)) for p in people)

    return render(
        request,
        "expense_tracker/dashboard.html",
        {
            "mellat_balance": mellat_balance(),
            "today_total": _sum_expenses(today_qs),
            "week_total": _sum_expenses(week_qs),
            "month_total": _sum_expenses(month_qs),
            "month_label": month_label,
            "today_j": format_jalali(today),
            "categories": active_categories,
            "recent_expenses": DailyExpense.objects.select_related("category")[:8],
            "category_rows": _category_rows(month_qs),
            "seven_days": day_rows,
            "receivable_people": sorted(people, key=lambda p: p.outstanding, reverse=True)[:5],
            "receivable_total": total_receivable,
        },
    )


@login_required
def expense_list(request):
    qs = DailyExpense.objects.select_related("category")
    category_id = str(request.GET.get("category") or "").strip()
    if category_id.isdigit():
        qs = qs.filter(category_id=int(category_id))

    query = str(request.GET.get("q") or "").strip()
    if query:
        qs = qs.filter(title__icontains=query) | qs.filter(note__icontains=query)

    return render(
        request,
        "expense_tracker/expenses.html",
        {
            "expenses": qs[:250],
            "categories": ExpenseCategory.objects.all(),
            "selected_category": category_id,
            "query": query,
            "total": _sum_expenses(qs),
            "today_j": format_jalali(date.today()),
        },
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
        expense = create_expense(
            expense_date=_jalali_date(request.POST.get("date")),
            amount=_money(request.POST.get("amount")),
            category=category,
            title=request.POST.get("title"),
            note=request.POST.get("note"),
        )
        if wants_json:
            payload = _dashboard_totals()
            payload.update(
                {
                    "ok": True,
                    "message": "خرج ثبت شد؛ تاریخ برای ثبت بعدی ثابت ماند.",
                    "expense": {
                        "id": expense.id,
                        "title": expense.title or category.name,
                        "amount": int(expense.amount or 0),
                        "date": format_jalali(expense.date),
                        "category": category.name,
                        "accent": category.accent,
                    },
                }
            )
            return JsonResponse(payload)
        messages.success(request, "هزینه ثبت شد و به همان مبلغ از موجودی ملت کم شد.")
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
    expense = get_object_or_404(DailyExpense.objects.select_related("category"), id=expense_id)
    if request.method == "POST":
        try:
            category = get_object_or_404(
                ExpenseCategory,
                id=int(request.POST.get("category") or 0),
            )
            update_expense(
                expense,
                expense_date=_jalali_date(request.POST.get("date")),
                amount=_money(request.POST.get("amount")),
                category=category,
                title=request.POST.get("title"),
                note=request.POST.get("note"),
            )
            messages.success(request, "هزینه ویرایش شد و اختلاف مبلغ روی ملت اعمال شد.")
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
        },
    )


@login_required
@require_POST
def expense_delete(request, expense_id):
    expense = get_object_or_404(DailyExpense, id=expense_id)
    try:
        amount = int(expense.amount or 0)
        delete_expense(expense)
        messages.success(request, f"هزینه حذف شد و {amount:,} تومان به ملت برگشت.")
    except Exception as exc:
        messages.error(request, f"حذف انجام نشد: {exc}")
    return redirect(request.POST.get("next") or "expense_tracker:expense_list")


@login_required
def receivables(request):
    people = _receivable_people()
    return render(
        request,
        "expense_tracker/receivables.html",
        {
            "people": sorted(people, key=lambda p: (p.outstanding, p.name), reverse=True),
            "entries": ReceivableEntry.objects.select_related("person")[:120],
            "today_j": format_jalali(date.today()),
            "total_outstanding": sum(max(0, p.outstanding) for p in people),
            "mellat_balance": mellat_balance(),
        },
    )


@login_required
@require_POST
def receivable_person_add(request):
    try:
        name = re.sub(r"\s+", " ", str(request.POST.get("name") or "")).strip()
        if not name:
            raise ValueError("نام شخص خالی است.")
        person, created = ReceivablePerson.objects.get_or_create(
            name=name,
            defaults={"note": str(request.POST.get("note") or "").strip()[:250]},
        )
        if not created and not person.active:
            person.active = True
            person.save(update_fields=["active"])
        messages.success(request, "شخص به لیست طلب‌ها اضافه شد.")
    except Exception as exc:
        messages.error(request, f"شخص اضافه نشد: {exc}")
    return redirect("expense_tracker:receivables")


@login_required
@require_POST
def receivable_claim_add(request, person_id):
    person = get_object_or_404(ReceivablePerson, id=person_id, active=True)
    try:
        create_claim(
            person=person,
            entry_date=_jalali_date(request.POST.get("date")),
            amount=_money(request.POST.get("amount")),
            note=request.POST.get("note"),
        )
        messages.success(request, f"طلب از {person.name} ثبت شد.")
    except Exception as exc:
        messages.error(request, f"طلب ثبت نشد: {exc}")
    return redirect("expense_tracker:receivables")


@login_required
@require_POST
def receivable_repay(request, person_id):
    person = get_object_or_404(ReceivablePerson, id=person_id, active=True)
    try:
        entry = record_repayment(
            person=person,
            entry_date=_jalali_date(request.POST.get("date")),
            amount=_money(request.POST.get("amount")),
            note=request.POST.get("note"),
        )
        messages.success(
            request,
            f"{entry.amount:,} تومان تسویه شد؛ همین مبلغ به موجودی ملت اضافه شد.",
        )
    except Exception as exc:
        messages.error(request, f"تسویه ثبت نشد: {exc}")
    return redirect("expense_tracker:receivables")


@login_required
@require_POST
def receivable_entry_delete(request, entry_id):
    entry = get_object_or_404(ReceivableEntry, id=entry_id)
    try:
        kind = entry.kind
        amount = int(entry.amount or 0)
        delete_receivable_entry(entry)
        if kind == ReceivableEntry.PAYMENT:
            messages.success(
                request,
                f"تسویه حذف شد و {amount:,} تومان دوباره از ملت کم شد.",
            )
        else:
            messages.success(request, "طلب حذف شد.")
    except Exception as exc:
        messages.error(request, f"حذف گردش طلب انجام نشد: {exc}")
    return redirect("expense_tracker:receivables")


@login_required
def categories(request):
    rows = list(ExpenseCategory.objects.all())
    for row in rows:
        row.expense_count = row.expenses.count()
        row.expense_total = int(row.expenses.aggregate(v=Sum("amount"))["v"] or 0)
    return render(
        request,
        "expense_tracker/categories.html",
        {"categories": rows, "accents": ACCENTS},
    )


@login_required
@require_POST
def category_add(request):
    try:
        name = re.sub(r"\s+", " ", str(request.POST.get("name") or "")).strip()
        if not name:
            raise ValueError("نام دسته خالی است.")
        if ExpenseCategory.objects.filter(name=name).exists():
            raise ValueError("این دسته از قبل وجود دارد.")
        base = slugify(name, allow_unicode=True) or "category"
        slug = base
        suffix = 2
        while ExpenseCategory.objects.filter(slug=slug).exists():
            slug = f"{base}-{suffix}"
            suffix += 1
        accent = str(request.POST.get("accent") or "green")
        if accent not in ACCENTS:
            accent = "green"
        order = (ExpenseCategory.objects.aggregate(v=Sum("sort_order"))["v"] or 0) + 10
        ExpenseCategory.objects.create(
            name=name,
            slug=slug,
            accent=accent,
            active=True,
            sort_order=order,
        )
        messages.success(request, "دسته جدید اضافه شد.")
    except Exception as exc:
        messages.error(request, f"دسته اضافه نشد: {exc}")
    return redirect("expense_tracker:categories")


@login_required
@require_POST
def category_toggle(request, category_id):
    category = get_object_or_404(ExpenseCategory, id=category_id)
    category.active = not category.active
    category.save(update_fields=["active"])
    messages.success(request, "وضعیت دسته تغییر کرد.")
    return redirect("expense_tracker:categories")


@login_required
@require_POST
def category_delete(request, category_id):
    category = get_object_or_404(ExpenseCategory, id=category_id)
    try:
        if category.expenses.exists():
            raise ValueError("این دسته هزینه ثبت‌شده دارد؛ می‌توانی غیرفعالش کنی ولی حذف نه.")
        category.delete()
        messages.success(request, "دسته حذف شد.")
    except Exception as exc:
        messages.error(request, f"دسته حذف نشد: {exc}")
    return redirect("expense_tracker:categories")


@login_required
def reports(request):
    today = date.today()
    month_start, month_next, month_label = _current_month_range(today)
    month_qs = DailyExpense.objects.filter(date__gte=month_start, date__lt=month_next)

    daily_rows = list(
        month_qs.values("date").annotate(total=Sum("amount")).order_by("date")
    )
    max_total = max((int(row["total"] or 0) for row in daily_rows), default=0)
    for row in daily_rows:
        row["total"] = int(row["total"] or 0)
        row["jalali"] = format_jalali(row["date"])
        row["pct"] = round(row["total"] * 100 / max_total, 1) if max_total else 0

    return render(
        request,
        "expense_tracker/reports.html",
        {
            "month_label": month_label,
            "month_total": _sum_expenses(month_qs),
            "category_rows": _category_rows(month_qs),
            "daily_rows": daily_rows,
            "expense_count": month_qs.count(),
        },
    )
