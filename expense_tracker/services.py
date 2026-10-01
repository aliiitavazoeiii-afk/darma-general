from django.db import transaction
from django.db.models import Sum

from core.payment_source_v63 import (
    SOURCE_MELAT,
    normalize_source,
    source_balance,
    source_row,
)

from .models import DailyExpense, ReceivableEntry, ReceivablePerson


def mellat_balance():
    return int(source_balance(SOURCE_MELAT) or 0)


def _positive_amount(value, label="مبلغ"):
    amount = int(value or 0)
    if amount <= 0:
        raise ValueError(f"{label} باید بیشتر از صفر باشد.")
    return amount


def _lock_sources(*sources):
    locked = {}
    for source in sorted({normalize_source(source) for source in sources}):
        row = source_row(source, create=True, for_update=True)
        if row is None:
            raise RuntimeError("حساب مبدا پرداخت پیدا نشد.")
        locked[source] = row
    return locked


def _lock_mellat():
    return _lock_sources(SOURCE_MELAT)[SOURCE_MELAT]


@transaction.atomic
def create_expense(
    *,
    expense_date,
    amount,
    category,
    payment_source=SOURCE_MELAT,
    title="",
    note="",
):
    amount = _positive_amount(amount, "مبلغ هزینه")
    payment_source = normalize_source(payment_source)
    account = _lock_sources(payment_source)[payment_source]
    expense = DailyExpense.objects.create(
        date=expense_date,
        amount=amount,
        category=category,
        payment_source=payment_source,
        title=(title or "").strip()[:160],
        note=(note or "").strip(),
    )
    account.amount = int(account.amount or 0) - amount
    account.save(update_fields=["amount", "updated_at"])
    return expense


@transaction.atomic
def update_expense(
    expense,
    *,
    expense_date,
    amount,
    category,
    payment_source=None,
    title="",
    note="",
):
    amount = _positive_amount(amount, "مبلغ هزینه")
    expense = DailyExpense.objects.select_for_update().get(pk=expense.pk)
    old_amount = int(expense.amount or 0)
    old_source = normalize_source(expense.payment_source)
    new_source = normalize_source(payment_source or old_source)
    accounts = _lock_sources(old_source, new_source)

    expense.date = expense_date
    expense.amount = amount
    expense.category = category
    expense.payment_source = new_source
    expense.title = (title or "").strip()[:160]
    expense.note = (note or "").strip()
    expense.save()

    if old_source == new_source:
        account = accounts[new_source]
        account.amount = int(account.amount or 0) + old_amount - amount
        account.save(update_fields=["amount", "updated_at"])
    else:
        old_account = accounts[old_source]
        new_account = accounts[new_source]
        old_account.amount = int(old_account.amount or 0) + old_amount
        new_account.amount = int(new_account.amount or 0) - amount
        old_account.save(update_fields=["amount", "updated_at"])
        new_account.save(update_fields=["amount", "updated_at"])
    return expense


@transaction.atomic
def delete_expense(expense):
    expense = DailyExpense.objects.select_for_update().get(pk=expense.pk)
    amount = int(expense.amount or 0)
    payment_source = normalize_source(expense.payment_source)
    account = _lock_sources(payment_source)[payment_source]
    expense.delete()
    account.amount = int(account.amount or 0) + amount
    account.save(update_fields=["amount", "updated_at"])


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
    mellat = _lock_mellat()
    entry = ReceivableEntry.objects.create(
        person=person,
        date=entry_date,
        kind=ReceivableEntry.CLAIM,
        amount=amount,
        note=(note or "").strip()[:250],
        mellat_applied=True,
    )
    mellat.amount = int(mellat.amount or 0) - amount
    mellat.save(update_fields=["amount", "updated_at"])
    return entry


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
        mellat_applied=True,
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
        if entry.mellat_applied:
            mellat = _lock_mellat()
            entry.delete()
            mellat.amount = int(mellat.amount or 0) - amount
            mellat.save(update_fields=["amount", "updated_at"])
        else:
            entry.delete()
        return

    claim, payment, _outstanding = _totals_for_person(person)
    if claim - amount < payment:
        raise ValueError(
            "این طلب را نمی‌توان حذف کرد چون بخشی از آن قبلاً تسویه شده است."
        )

    if entry.mellat_applied:
        mellat = _lock_mellat()
        entry.delete()
        mellat.amount = int(mellat.amount or 0) + amount
        mellat.save(update_fields=["amount", "updated_at"])
    else:
        entry.delete()
