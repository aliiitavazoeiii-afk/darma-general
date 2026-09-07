from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import business_receipts_v64 as receipts_v64
from . import business_tools_v21 as v21
from . import business_tools_v60 as v60
from .dateutils import format_jalali, parse_jalali_date
from .excel_views import _int
from .dia_gallery_v45 import dia_gallery_receivable_total
from .finance_excel_v9 import digikala_receivable_total
from .material_flow import COLOR_LABELS
from .material_purchase_v14 import purchase_data_for_payment
from .models import BusinessPayment, DigikalaSettlement
from .payment_source_v63 import (
    SOURCE_CHOICES,
    SOURCE_LABELS,
    SOURCE_MELAT,
    SOURCE_MOFID,
    adjust_source_account,
    normalize_source,
    source_balance,
)
from .self_spend_v62 import SELF_PAYEE, adjust_self_tracking


# V62: Pedram is the same business counterparty as tailor. Keep legacy rows readable,
# but do not offer Pedram as a new payment target anymore.
PAYEE_CHOICES = [(key, label) for key, label in v60.PAYEE_CHOICES if key != "pedram"]
if SELF_PAYEE not in {key for key, _label in PAYEE_CHOICES}:
    PAYEE_CHOICES.append((SELF_PAYEE, "خودم"))
PAYEE_LABELS = dict(v60.PAYEE_LABELS)
PAYEE_LABELS["pedram"] = "خیاط"
PAYEE_LABELS[SELF_PAYEE] = "خودم"
MATERIAL_PAYEES = v60.MATERIAL_PAYEES


def _parse_payment_post(post, default_source=SOURCE_MELAT):
    source = normalize_source(post.get("source_account") or default_source)
    payee = (post.get("payee") or "").strip()

    # Old edit forms / legacy callers may still carry pedram. Normalize it to tailor.
    if payee == "pedram":
        post = post.copy()
        post["payee"] = "tailor"
        payee = "tailor"

    if payee == SELF_PAYEE:
        payment_date = parse_jalali_date(post.get("date") or format_jalali(date.today()))
        note = (post.get("note") or "").strip()[:250]
        paid_amount = _int(post.get("amount"))
        if paid_amount <= 0:
            raise ValueError("مبلغ پرداخت به خودم باید بیشتر از صفر باشد.")
        return {
            "date": payment_date,
            "payee": SELF_PAYEE,
            "paid": int(paid_amount),
            "note": note or "برداشت شخصی",
            "purchase": None,
            "invoice": 0,
            "prepayment_title": None,
            "source_account": source,
        }

    if payee not in {key for key, _label in PAYEE_CHOICES}:
        raise ValueError("دریافت‌کننده پرداخت معتبر نیست.")
    parsed = v60._parse_payment_post(post)
    parsed["source_account"] = source
    return parsed


def _payment_source(payment):
    return normalize_source(getattr(payment, "source_account", SOURCE_MELAT))


def _reroute_legacy_apply_from_mellat(payment):
    """V60 applies cash to Mellat; move that exact debit to the selected source."""
    source = _payment_source(payment)
    if source == SOURCE_MELAT:
        return
    amount = int(payment.amount or 0)
    adjust_source_account(SOURCE_MELAT, amount)
    adjust_source_account(source, -amount)


def _reroute_legacy_reverse_from_mellat(payment):
    """V60 reverse restores Mellat; move that exact restoration to the original source."""
    source = _payment_source(payment)
    if source == SOURCE_MELAT:
        return
    amount = int(payment.amount or 0)
    adjust_source_account(SOURCE_MELAT, -amount)
    adjust_source_account(source, amount)


def _apply_full(payment, parsed):
    v60._apply_full(payment, parsed)
    _reroute_legacy_apply_from_mellat(payment)
    if payment.payee == SELF_PAYEE:
        adjust_self_tracking(int(payment.amount or 0))


def _reverse_full(payment):
    if payment.payee == SELF_PAYEE:
        adjust_self_tracking(-int(payment.amount or 0))
    v60._reverse_full(payment)
    _reroute_legacy_reverse_from_mellat(payment)


def _apply_material_purchase_finance_only(payment):
    v60.v22._apply_material_purchase_finance_only(payment)
    _reroute_legacy_apply_from_mellat(payment)


def _reverse_material_purchase_finance_only(payment):
    v60.v22._reverse_material_purchase_finance_only(payment)
    _reroute_legacy_reverse_from_mellat(payment)


def _save_payment_fields(payment, parsed):
    v60._save_payment_fields(payment, parsed)
    payment.source_account = normalize_source(parsed.get("source_account"))
    payment.save(update_fields=["source_account"])


def _payment_rows():
    rows = v60._payment_rows()
    for row in rows:
        row.payee_label = PAYEE_LABELS.get(row.payee, row.payee)
        row.source_account_label = SOURCE_LABELS.get(_payment_source(row), "ملت")
    return rows


@login_required
def payments(request):
    section = (request.GET.get("section") or "").strip().lower()
    if section not in {"payments", "receipts"}:
        section = ""

    month_start, month_next, month_label = v21._current_jalali_month_range()
    payment_month_total = int(
        BusinessPayment.objects.filter(date__gte=month_start, date__lt=month_next).aggregate(v=Sum("amount"))["v"] or 0
    )
    receipt_month_total = int(
        DigikalaSettlement.objects.filter(date__gte=month_start, date__lt=month_next).aggregate(v=Sum("amount"))["v"] or 0
    )

    payment_rows = _payment_rows() if section == "payments" else []
    elastic_multi_payloads = {
        str(row.id): row.purchase_data
        for row in payment_rows
        if (row.purchase_data or {}).get("k") == v60.MULTI_KIND
    }
    payment_source_payloads = {
        str(row.id): _payment_source(row)
        for row in payment_rows
    }
    return render(
        request,
        "core/payments_v62.html",
        {
            "section": section,
            "payment_rows": payment_rows,
            "elastic_multi_payloads": elastic_multi_payloads,
            "payment_source_payloads": payment_source_payloads,
            "receipt_rows": receipts_v64.receipt_rows() if section == "receipts" else [],
            "today_j": format_jalali(date.today()),
            "mellat_balance": v21.mellat_balance(),
            "mofid_balance": source_balance(SOURCE_MOFID),
            "tailor_balance": v21.tailor_balance(),
            "takvin_debt": int(v21._takvin_setting().value or 0),
            "digikala_receivable": digikala_receivable_total(),
            "dia_gallery_receivable": dia_gallery_receivable_total(),
            "receipt_source_choices": receipts_v64.SOURCE_CHOICES,
            "payees": PAYEE_CHOICES,
            "payment_source_choices": SOURCE_CHOICES,
            "material_colors": list(COLOR_LABELS.items()),
            "payment_month_total": payment_month_total,
            "receipt_month_total": receipt_month_total,
            "month_label": month_label,
        },
    )


@login_required
@require_POST
def payment_add(request):
    try:
        parsed = _parse_payment_post(request.POST)
        with transaction.atomic():
            payment = BusinessPayment.objects.create(
                date=parsed["date"],
                payee=parsed["payee"],
                source_account=parsed["source_account"],
                amount=parsed["paid"],
                note=v60.encode_purchase_note(parsed["purchase"]) if parsed["purchase"] else parsed["note"],
            )
            _apply_full(payment, parsed)
        source_label = SOURCE_LABELS[parsed["source_account"]]
        if parsed["payee"] == SELF_PAYEE:
            messages.success(
                request,
                f"پرداخت به خودم {parsed['paid']:,} تومان از حساب {source_label} ثبت شد؛ سرمایه به همین مقدار کم شد و حساب «خودم» به همین مقدار زیاد شد.",
            )
        elif parsed["purchase"]:
            messages.success(
                request,
                f"پرداخت از حساب {source_label} ثبت شد؛ ارزش خرید {v60._invoice_value(parsed['purchase']):,} تومان و پرداخت واقعی {parsed['paid']:,} تومان بود. موجودی مواد هم اعمال شد.",
            )
        else:
            messages.success(request, f"پرداخت از حساب {source_label} ثبت شد.")
    except Exception as exc:
        messages.error(request, f"پرداخت ثبت نشد و کل عملیات برگشت: {exc}")
    return redirect("/payments/?section=payments")


@login_required
@require_POST
def payment_update(request, payment_id):
    try:
        with transaction.atomic():
            payment = get_object_or_404(BusinessPayment.objects.select_for_update(), id=payment_id)
            parsed = _parse_payment_post(request.POST, default_source=_payment_source(payment))
            old_purchase = purchase_data_for_payment(payment) if payment.payee in MATERIAL_PAYEES else None
            same_purchase = bool(
                old_purchase
                and parsed["purchase"]
                and payment.payee == parsed["payee"]
                and v60._purchase_signature(old_purchase) == v60._purchase_signature(parsed["purchase"])
            )

            if same_purchase:
                _reverse_material_purchase_finance_only(payment)
                _save_payment_fields(payment, parsed)
                v60.create_purchase_ledger(payment, parsed["purchase"])
                _apply_material_purchase_finance_only(payment)
            else:
                _reverse_full(payment)
                _save_payment_fields(payment, parsed)
                _apply_full(payment, parsed)
        messages.success(request, "پرداخت ویرایش شد؛ حساب مبدا، اثر مالی و موجودی به‌صورت اتمیک همگام شد.")
    except Exception as exc:
        messages.error(request, f"ویرایش پرداخت انجام نشد و کل عملیات برگشت: {exc}")
    return redirect("/payments/?section=payments")


@login_required
@require_POST
def payment_delete(request, payment_id):
    try:
        with transaction.atomic():
            payment = get_object_or_404(BusinessPayment.objects.select_for_update(), id=payment_id)
            was_self = payment.payee == SELF_PAYEE
            amount = int(payment.amount or 0)
            source_label = SOURCE_LABELS.get(_payment_source(payment), "ملت")
            _reverse_full(payment)
            payment.delete()
        if was_self:
            messages.success(
                request,
                f"پرداخت به خودم {amount:,} تومان حذف شد؛ مبلغ به حساب {source_label} برگشت و از حساب «خودم» کم شد.",
            )
        else:
            messages.success(request, f"پرداخت حذف شد و اثر مالی/موجودی خودش به حساب {source_label} برگشت.")
    except Exception as exc:
        messages.error(request, f"پرداخت حذف نشد: {exc}")
    return redirect("/payments/?section=payments")
