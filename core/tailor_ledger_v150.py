"""Read-only complete available tailor account audit (V150).

The live signed tailor/person balance is authoritative:
  negative = our debt to tailor; positive = advance/receivable from tailor.
Historical direct manual balance edits were never event-sourced; therefore
the residual opening balance is MATHEMATICALLY RECONSTRUCTED, not falsely
described as an original audited opening balance.

Legacy Account.PEDRAM is a *different* account; show its ledger separately
rather than silently combining both in financial statements.
"""
from collections import defaultdict
from datetime import date
from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .business_tools_v14 import _tailor_row
from .dateutils import format_jalali
from .final_services import account_balance
from .models import (
    Account, AccountEntry, BusinessPayment, MaterialReportBlock,
    MoneyMovement, TailorBalanceEntry, WholesaleInvoice,
)


def live_tailor_balance():
    row = _tailor_row(create=False)
    return int(row.amount or 0) if row else 0


def _line(when, origin, key, title, delta, note="", detail=""):
    return {
        "date": when, "date_j": format_jalali(when) if when else "",
        "origin": origin, "ref": str(key), "title": title,
        "delta": int(delta), "note": str(note or ""), "detail": str(detail or ""),
    }


def _running(entries, opening):
    balance = int(opening)
    result = []
    for row in sorted(entries, key=lambda e: (
        e["date"] or date.min, e["origin"], e["ref"],
    )):
        balance += int(row["delta"])
        result.append({
            **row, "balance": balance,
            "debt": max(0, -balance), "credit": max(0, balance),
            "payment": max(0, int(row["delta"])),
            "charge": max(0, -int(row["delta"])),
        })
    return result, balance


def build_tailor_ledger():
    """No filters or limits: export and page cover ALL retained source records."""
    current = live_tailor_balance()
    entries = []

    for pay in BusinessPayment.objects.filter(
        payee__in=[BusinessPayment.TAILOR, BusinessPayment.PEDRAM]
    ).order_by("date", "id"):
        label = "واریزی به خیاط" if pay.payee == BusinessPayment.TAILOR else "پرداخت قدیمی به پدرام"
        entries.append(_line(
            pay.date, "payment", pay.pk, label,
            int(pay.amount or 0), pay.note,
            f"حساب پرداخت: {pay.source_account or 'melat'}",
        ))

    for block in (
        MaterialReportBlock.objects.select_related("brand")
        .prefetch_related("output_applications").order_by("date", "id")
    ):
        applied_qty = sum(
            max(0, int(row.quantity or 0))
            for row in block.output_applications.all()
        )
        # A drafted form can have delivery_wage even before applying finished
        # goods. Only a sheet with ACTUALLY APPLIED delivery contributes here.
        if applied_qty <= 0:
            continue
        posted_wage = max(0, int(block.delivery_wage or 0))
        entries.append(_line(
            block.date, "production", block.pk,
            f"مزد خیاط · صورت {block.pk} · {block.brand.name}",
            -posted_wage,
            block.title or block.note,
            f"{applied_qty} عدد تحویل اعمال‌شده؛ تاریخ، تاریخ صورت است نه الزاماً تاریخ اعمال",
        ))

    for invoice in (
        WholesaleInvoice.objects.filter(customer__is_pedram=True)
        .select_related("customer").order_by("date", "id")
    ):
        # The signed tailor person row is increased by the whole invoice gross
        # (a wholesale receivable / offset against tailor debt), not by a bank
        # payment. A historic tailor_deducted_amount is listed as metadata.
        entries.append(_line(
            invoice.date, "wholesale", invoice.pk,
            f"فاکتور عمده‌فروشی پدرام #{invoice.pk}",
            int(invoice.total_amount or 0),
            invoice.note,
            f"{int(invoice.quantity_total or 0)} عدد؛ تهاتر تاریخی ثبت‌شده: {int(invoice.tailor_deducted_amount or 0):,}",
        ))

    # No immutable historical snapshot of manual account edits existed before
    # V150. The residual is an explicit reconciliation, not fabricated history.
    observed_delta = sum(row["delta"] for row in entries)
    reconciled_opening = current - observed_delta
    running, computed = _running(entries, reconciled_opening)
    assert computed == current
    base = _tailor_row(create=False)

    # Additional legacy event table may duplicate operations represented in
    # production/payment records. Show unaggregated for audit, never sum it
    # again into the signed person balance.
    legacy_events = [
        _line(row.date, "legacy-tailor-entry", row.pk, row.title, row.delta, "", row.reference)
        for row in TailorBalanceEntry.objects.all().order_by("date", "id")
    ]

    # Separate historical Pedram Account (AccountEntry + MoneyMovement), whose
    # balance has a different canonical source from ExcelManualRow(PERSONS).
    account = Account.objects.filter(key=Account.PEDRAM).first()
    old_rows = []
    old_opening = 0
    if account:
        old_opening = int(account.opening_balance or 0)
        for entry in AccountEntry.objects.filter(account=account).order_by("date", "id"):
            old_rows.append(_line(
                entry.date, "account-entry", entry.pk, entry.title,
                entry.delta, entry.note, entry.reference,
            ))
        for m in MoneyMovement.objects.filter(
            to_account=account
        ).order_by("date", "id"):
            old_rows.append(_line(m.date, "money-in", m.pk, m.title, int(m.amount), m.note, m.kind))
        for m in MoneyMovement.objects.filter(
            from_account=account
        ).order_by("date", "id"):
            old_rows.append(_line(m.date, "money-out", m.pk, m.title, -int(m.amount), m.note, m.kind))
    old_running, old_ending = _running(old_rows, old_opening)
    old_current = account_balance(account) if account else 0
    assert old_current == old_ending

    totals = {
        "wage": sum(-row["delta"] for row in entries if row["origin"] == "production"),
        "payments": sum(row["delta"] for row in entries if row["origin"] == "payment"),
        "wholesale": sum(row["delta"] for row in entries if row["origin"] == "wholesale"),
    }

    return {
        "current": current,
        "debt": max(0, -current),
        "advance": max(0, current),
        "base_reconstructed": reconciled_opening,
        "base_date": base.created_at.date() if base else None,
        "base_changed": bool(base and base.updated_at != base.created_at),
        "entries": running,
        "totals": totals,
        "legacy_events": legacy_events,
        "legacy_account_current": old_current,
        "legacy_account_opening": old_opening,
        "legacy_account_entries": old_running,
        "legacy_account_present": bool(account),
    }


def _xlsx_safe(value):
    if value is None:
        return ""
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r", "\n")):
        return "'" + value
    return value


def _style_sheet(ws, *, money_columns=()):
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    ws.sheet_view.rightToLeft = True
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for cell in ws[1]:
        cell.fill = PatternFill(fill_type="solid", fgColor="10263D")
        cell.font = Font(name="Tahoma", bold=True, color="FFFFFF", size=11)
        cell.alignment = Alignment(horizontal="right", vertical="center")
    ws.row_dimensions[1].height = 28
    for col in range(1, ws.max_column + 1):
        width = 17
        if col in (3, 4, 9):
            width = 30
        if col == 8:
            width = 48
        ws.column_dimensions[get_column_letter(col)].width = width
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(horizontal="right", vertical="center")
            if cell.column in money_columns and isinstance(cell.value, int):
                cell.number_format = '#,##0;[Red](#,##0)'
        if row[0].row % 2 == 0:
            for cell in row:
                cell.fill = PatternFill(fill_type="solid", fgColor="EAF3F9")


def _write_ledger(ws, rows, opening, heading, *, reconstructed=False):
    ws.append(["تاریخ شمسی", "نوع رویداد", "عنوان", "مبلغ افزایش طلب ما",
               "مبلغ افزایش بدهی ما", "مانده امضادار", "بدهی به خیاط",
               "یادداشت", "شناسه / منبع"])
    label = "مانده اولیه بازسازی‌شده، نه سند افتتاحیه قطعی" if reconstructed else "مانده افتتاحیه ثبت‌شده"
    ws.append(["", "افتتاحیه", _xlsx_safe(label), 0, 0,
               int(opening), max(0, -int(opening)), "", "opening"])
    for e in rows:
        ws.append([
            e["date_j"], _xlsx_safe(e["origin"]), _xlsx_safe(e["title"]),
            int(e["payment"]), int(e["charge"]), int(e["balance"]),
            int(e["debt"]), _xlsx_safe(e["note"]),
            _xlsx_safe(e["origin"] + ":" + e["ref"] + " " + e["detail"]),
        ])
    _style_sheet(ws, money_columns=(4, 5, 6, 7))


@login_required
@require_GET
def tailor_ledger(request):
    return render(request, "core/tailor_ledger_v150.html", build_tailor_ledger())


@login_required
@require_GET
def tailor_ledger_xlsx(request):
    """Export ALL retained events, even when there are thousands of rows."""
    from openpyxl import Workbook
    wb = Workbook()
    data = build_tailor_ledger()
    sheet = wb.active
    sheet.title = "گردش حساب خیاط"
    _write_ledger(sheet, data["entries"], data["base_reconstructed"],
                  "حساب خیاط", reconstructed=True)
    legacy = wb.create_sheet("حساب پدرام قدیمی")
    _write_ledger(legacy, data["legacy_account_entries"],
                  data["legacy_account_opening"], "حساب پدرام قدیمی")

    audit = wb.create_sheet("سوابق مستقل خیاط")
    audit.append(["تاریخ شمسی", "نوع", "عنوان", "تغییر امضادار", "مرجع"])
    for e in data["legacy_events"]:
        audit.append([
            e["date_j"], _xlsx_safe(e["origin"]), _xlsx_safe(e["title"]),
            int(e["delta"]), _xlsx_safe(e["detail"]),
        ])
    _style_sheet(audit, money_columns=(4,))

    meta = wb.create_sheet("راهنما و تطبیق")
    notes = [
        ("مانده فعلی حساب شخص خیاط", data["current"]),
        ("بدهی ما به خیاط (اگر مثبت)", data["debt"]),
        ("طلب یا پیش‌پرداخت ما نزد خیاط", data["advance"]),
        ("مانده آغازین بازسازی‌شده", data["base_reconstructed"]),
        ("جمع مزد صورت‌های دارای تحویل اعمال‌شده", data["totals"]["wage"]),
        ("جمع واریزی ثبت‌شده به خیاط", data["totals"]["payments"]),
        ("جمع فاکتور عمده‌فروشی پدرام", data["totals"]["wholesale"]),
        ("مانده حساب مستقل قدیمی پدرام", data["legacy_account_current"]),
        ("محدودیت تاریخی",
         "مانده افتتاحیه اصلی و ویرایش‌های دستی قدیمی در سیستم رویداد مستقل و کامل ندارند؛ "
         "مانده افتتاحیه این گزارش از مانده فعلی منهای گردش قابل ردیابی بازسازی شده است."),
        ("نکته مزد",
         "مبلغ مزد از delivery_wage صورت‌های دارای تحویل اعمال‌شده خوانده می‌شود؛ "
         "در صورت اصلاح قدیمی بدون تاریخچه، تاریخ و مبلغ اولیه دقیق قابل بازیابی نیست."),
        ("حساب قدیمی پدرام",
         "حساب قدیمی Account.PEDRAM جدا از ExcelManualRow خیاط است؛ برای جلوگیری از "
         "دوباره‌شماری مجموع این دو مانده به‌عنوان یک بدهی نمایش داده نمی‌شود."),
        ("سوابق مستقل",
         "TailorBalanceEntry صرفاً برای بررسی صادر شده؛ چون پیوند قطعی آن با "
         "گردش اصلی مشخص نیست، مجدداً در مانده خیاط جمع نمی‌شود."),
    ]
    meta.append(["عنوان", "مقدار یا توضیح"])
    for item in notes:
        meta.append([_xlsx_safe(item[0]), _xlsx_safe(item[1])])
    _style_sheet(meta, money_columns=(2,))
    meta.column_dimensions["B"].width = 102

    buffer = BytesIO()
    wb.save(buffer)
    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="darma-tailor-ledger-v150.xlsx"'
    response["Cache-Control"] = "private, no-store"
    return response
