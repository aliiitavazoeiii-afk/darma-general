"""V150 read-only tailor account statement and Excel export.

Important provenance: the live tailor balance is stored as a mutable
ExcelManualRow amount. The original manually entered opening balance and
subsequent manual corrections were not stored in an immutable ledger.
Reconstruct an explicit *implied* opening from current balance and observable
payments and applied production wage snapshots. Never call it verified.
"""
from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

from .business_tools_v14 import _tailor_row
from .dateutils import format_jalali
from .material_report_v23 import _material_label
from .models import BusinessPayment, MaterialReportBlock


def build_tailor_statement():
    account = _tailor_row(create=False)
    closing = int(account.amount or 0) if account else 0
    items = []
    missing_wages = []
    for payment in BusinessPayment.objects.filter(payee__in=("tailor", "pedram")).order_by("date", "id"):
        amount = int(payment.amount or 0)
        if amount <= 0:
            continue
        source = dict(BusinessPayment.SOURCE_CHOICES).get(payment.source_account, payment.source_account)
        items.append({
            "date": payment.date, "date_j": format_jalali(payment.date),
            "kind": "واریزی به خیاط", "reference": f"پرداخت #{payment.pk}",
            "description": (payment.note or "پرداخت ثبت‌شده") + f" · منبع: {source}",
            "increase": amount, "decrease": 0, "delta": amount,
            "sort": (payment.date, 1, payment.pk),
        })
    blocks = MaterialReportBlock.objects.select_related("brand").prefetch_related(
        "output_applications"
    ).all()
    for block in blocks:
        applied = [row for row in block.output_applications.all() if int(row.quantity or 0) > 0]
        if not applied:
            continue
        pieces = sum(int(row.quantity) for row in applied)
        wage = max(0, int(block.delivery_wage or 0))
        if wage == 0:
            # A historical wage cannot be inferred reliably from today's rate.
            missing_wages.append(block.pk)
            continue
        details = "؛ ".join(
            f"{_material_label(row.model_key)} / {row.size_key.upper()}: {int(row.quantity)} عدد"
            for row in sorted(applied, key=lambda x: (x.model_key, x.size_key))
        )
        items.append({
            "date": block.date, "date_j": format_jalali(block.date),
            "kind": "مزد تولید و تحویل", "reference": f"صورت #{block.pk}",
            "description": f"{block.brand.name} · {pieces:,} عدد · {details}",
            "increase": 0, "decrease": wage, "delta": -wage,
            "sort": (block.date, 0, block.pk),
        })
    items.sort(key=lambda item: item["sort"])
    paid = sum(item["increase"] for item in items)
    wages = sum(item["decrease"] for item in items)
    opening = closing - paid + wages
    running = opening
    for item in items:
        running += item["delta"]
        item["balance"] = running
    return {
        "account_exists": bool(account),
        "opening": opening, "closing": closing,
        "payments": paid, "wages": wages,
        "rows": items, "count": len(items),
        "missing_wages": missing_wages,
        "is_reconstructed": True,
    }


@login_required
def tailor_statement(request):
    return render(request, "core/tailor_statement_v150.html", {
        "statement": build_tailor_statement()
    })


@login_required
def tailor_statement_excel(request):
    statement = build_tailor_statement()
    wb = Workbook()
    ws = wb.active
    ws.title = "گردش حساب خیاط"
    ws.sheet_view.rightToLeft = True
    ws.append(["گزارش کامل حساب خیاط ـ مبالغ به تومان"])
    ws.merge_cells("A1:G1")
    ws.append(["مانده اولیه بازسازی‌شده", statement["opening"], "کل پرداخت", statement["payments"],
               "کل مزد تولید", statement["wages"], "مانده فعلی"])
    ws.append(["", "", "", "", "", "", statement["closing"]])
    ws.append(["توجه: مانده اولیه از مانده جاری و رویدادهای قابل‌بازیابی استنتاج شده و لزوماً مبلغ افتتاحیه واقعی نیست."])
    ws.merge_cells("A4:G4")
    if statement["missing_wages"]:
        ws.append(["هشدار: برخی صورت‌ها تحویل اعمال‌شده دارند ولی مبلغ مزد ثبت‌شده آنها صفر است؛ آنها قابل محاسبه قطعی نیستند."])
        ws.merge_cells("A5:G5")
    ws.append([])
    ws.append(["تاریخ شمسی", "نوع رویداد", "شماره سند", "شرح کامل", "واریزی (+)", "مزد تولید (-)", "مانده طلب/بدهی"])
    header_row = ws.max_row
    ws.append(["—", "مانده اولیه بازسازی‌شده", "مبنای گزارش", "ارقام افتتاحیه قابل ممیزی مستقل نیستند", 0, 0, statement["opening"]])
    for item in statement["rows"]:
        ws.append([
            item["date_j"], item["kind"], item["reference"], item["description"],
            item["increase"], item["decrease"], item["balance"],
        ])
    ws.freeze_panes = f"A{header_row + 1}"
    ws.auto_filter.ref = f"A{header_row}:G{ws.max_row}"
    for col, width in enumerate((16, 25, 21, 74, 19, 19, 24), 1):
        ws.column_dimensions[get_column_letter(col)].width = width
    for cell in ws[header_row]:
        cell.fill = PatternFill("solid", fgColor="253C55")
        cell.font = Font(color="FFFFFF", bold=True)
        cell.alignment = Alignment(horizontal="right")
    for cell in ws[1]:
        cell.font = Font(bold=True, size=14, color="223D58")
    ws.row_dimensions[1].height = 30
    for row in ws.iter_rows(min_row=header_row + 1):
        for c in row:
            c.alignment = Alignment(vertical="center", horizontal="right")
        for c in row[4:7]:
            c.number_format = '#,##0;[Red](#,##0)'
    ws.column_dimensions["D"].width = 74
    out = BytesIO()
    wb.save(out)
    response = HttpResponse(
        out.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="tailor-statement-v150.xlsx"'
    return response
