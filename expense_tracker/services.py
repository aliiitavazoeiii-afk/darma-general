from django.db import transaction
from django.db.models import Sum

from core.payment_source_v63 import SOURCE_MELAT, source_balance, source_row

from .models import DailyExpense, ReceivableEntry, ReceivablePerson


def mellat_balance():
    return int(source_balance(SOURCE_MELAT) or 0)


def _positive_amount(value, label="مبلغ"):
    amount = int(value or 0)
    if amount <= 0:
        raise ValueError(f"{label} باید بیشتر از صفر باشد.")
    return amount


def _lock_mellat():
    row = source_row(SOURCE_MELAT, create=True, for_update=True)
    if row is None:
        raise RuntimeError("حساب ملت پیدا نشد.")
    return row


@transaction.atomic
def create_expense(*, expense_date, amount, category, title="", note=""):
    amount = _positive_amount(amount, "مبلغ هزینه")
    mellat = _lock_mellat()
    expense = DailyExpense.objects.create(
        date=expense_date,
        amount=amount,
        category=category,
        title=(title or "").strip()[:160],
        note=(note or "").strip(),
    )
    mellat.amount = int(mellat.amount or 0) - amount
    mellat.save(update_fields=["amount", "updated_at"])
    return expense


@transaction.atomic
def update_expense(expense, *, expense_date, amount, category, title="", note=""):
    amount = _positive_amount(amount, "مبلغ هزینه")
    expense = DailyExpense.objects.select_for_update().get(pk=expense.pk)
    old_amount = int(expense.amount or 0)
    mellat = _lock_mellat()

    expense.date = expense_date
    expense.amount = amount
    expense.category = category
    expense.title = (title or "").strip()[:160]
    expense.note = (note or "").strip()
    expense.save()

    mellat.amount = int(mellat.amount or 0) + old_amount - amount
    mellat.save(update_fields=["amount", "updated_at"])
    return expense


@transaction.atomic
def delete_expense(expense):
    expense = DailyExpense.objects.select_for_update().get(pk=expense.pk)
    amount = int(expense.amount or 0)
    mellat = _lock_mellat()
    expense.delete()
    mellat.amount = int(mellat.amount or 0) + amount
    mellat.save(update_fields=["amount", "updated_at"])


def _totals_for_person(person):
    rows = (
        ReceivableEntry.objects.filter(person=person)
        .values("kind")
        .annotate(total=Sum("amount"))
    )
    totals = {row["kind"]: int(row["total"] or 0) for row in rows}
    claim = totals.get(ReceivableEntry.CLAIM, 0)
    payment = totals.get(ReceivableEntry.PAYMENT, 0)
    return claim, payment, claim - payment


def outstanding_for_person(person):
    return _totals_for_person(person)[2]


@transaction.atomic
def create_claim(*, person, entry_date, amount, note=""):
    person = ReceivablePerson.objects.select_for_update().get(pk=person.pk)
    amount = _positive_amount(amount, "مبلغ طلب")
    return ReceivableEntry.objects.create(
        person=person,
        date=entry_date,
        kind=ReceivableEntry.CLAIM,
        amount=amount,
        note=(note or "").strip()[:250],
    )


@transaction.atomic
def record_repayment(*, person, entry_date, amount, note=""):
    person = ReceivablePerson.objects.select_for_update().get(pk=person.pk)
    amount = _positive_amount(amount, "مبلغ تسویه")
    _claim, _payment, outstanding = _totals_for_person(person)
    if amount > outstanding:
        raise ValueError("مبلغ تسویه از طلب باقی‌مانده بیشتر است.")

    mellat = _lock_mellat()
    entry = ReceivableEntry.objects.create(
        person=person,
        date=entry_date,
        kind=ReceivableEntry.PAYMENT,
        amount=amount,
        note=(note or "").strip()[:250],
    )
    mellat.amount = int(mellat.amount or 0) + amount
    mellat.save(update_fields=["amount", "updated_at"])
    return entry


@transaction.atomic
def delete_receivable_entry(entry):
    entry = (
        ReceivableEntry.objects.select_for_update()
        .select_related("person")
        .get(pk=entry.pk)
    )
    person = ReceivablePerson.objects.select_for_update().get(pk=entry.person_id)
    amount = int(entry.amount or 0)

    if entry.kind == ReceivableEntry.PAYMENT:
        mellat = _lock_mellat()
        entry.delete()
        mellat.amount = int(mellat.amount or 0) - amount
        mellat.save(update_fields=["amount", "updated_at"])
        return

    claim, payment, _outstanding = _totals_for_person(person)
    if claim - amount < payment:
        raise ValueError(
            "این طلب را نمی‌توان حذف کرد چون بخشی از آن قبلاً تسویه شده است."
        )
    entry.delete()
