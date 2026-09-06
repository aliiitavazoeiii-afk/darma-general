from django.db import transaction
from django.db.models import Sum

from .models import ExcelManualRow


SELF_PAYEE = "self"
SELF_ACCOUNT_TITLE = "خودم"
SELF_ACCOUNT_NOTE_PREFIX = "[system:self-spend-v62]"
SELF_ACCOUNT_NOTE = (
    SELF_ACCOUNT_NOTE_PREFIX
    + " جمع برداشت شخصی؛ این ردیف فقط برای رهگیری است و جزو سرمایه/دارایی حساب نمی‌شود."
)


def is_self_tracking_row(row):
    return bool(
        row
        and row.section == ExcelManualRow.ACCOUNTS
        and str(row.note or "").startswith(SELF_ACCOUNT_NOTE_PREFIX)
    )


def self_tracking_row(create=False, for_update=False):
    qs = ExcelManualRow.objects.filter(
        section=ExcelManualRow.ACCOUNTS,
        active=True,
        note__startswith=SELF_ACCOUNT_NOTE_PREFIX,
    ).order_by("id")
    if for_update:
        qs = qs.select_for_update()
    row = qs.first()
    if row or not create:
        return row

    order = (
        ExcelManualRow.objects.filter(section=ExcelManualRow.ACCOUNTS)
        .aggregate(v=Sum("sort_order"))["v"]
        or 0
    )
    row = ExcelManualRow.objects.create(
        section=ExcelManualRow.ACCOUNTS,
        title=SELF_ACCOUNT_TITLE,
        amount=0,
        sort_order=int(order) + 1,
        note=SELF_ACCOUNT_NOTE,
        active=True,
    )
    if for_update:
        row = ExcelManualRow.objects.select_for_update().get(pk=row.pk)
    return row


@transaction.atomic
def adjust_self_tracking(delta):
    delta = int(delta or 0)
    row = self_tracking_row(create=True, for_update=True)
    new_amount = int(row.amount or 0) + delta
    if new_amount < 0:
        raise ValueError(
            "جمع حساب «خودم» از مبلغ برگشتی کمتر است؛ عملیات برای جلوگیری از خرابی حساب متوقف شد."
        )
    row.amount = new_amount
    row.title = SELF_ACCOUNT_TITLE
    row.note = SELF_ACCOUNT_NOTE
    row.active = True
    row.save(update_fields=["amount", "title", "note", "active", "updated_at"])
    return row


def capital_accounts_queryset(qs=None):
    if qs is None:
        qs = ExcelManualRow.objects.filter(
            active=True,
            section=ExcelManualRow.ACCOUNTS,
        )
    return qs.exclude(note__startswith=SELF_ACCOUNT_NOTE_PREFIX)


def manual_accounts_capital_total():
    accounts = capital_accounts_queryset()
    persons = ExcelManualRow.objects.filter(
        active=True,
        section=ExcelManualRow.PERSONS,
    )
    return int(accounts.aggregate(v=Sum("amount"))["v"] or 0) + int(
        persons.aggregate(v=Sum("amount"))["v"] or 0
    )
