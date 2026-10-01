from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .dia_gallery_v45 import dia_gallery_receivable_total
from .finance_excel_v9 import digikala_ledger_total, digikala_receivable_total
from .models import ExcelManualRow, ExcelManualSetting
from .report_v10 import manual_report_action as report_manual_report_action
from .self_spend_v62 import capital_accounts_queryset


def _finance_account_context():
    """Canonical finance/account context reused by the hub and full accounts page.

    This intentionally reads the exact same ExcelManualRow / ExcelManualSetting
    sources that the comprehensive report has always used. No data is copied or
    migrated; V100 only makes the existing rows visible from Finance & Tools.
    """
    manual_rows = ExcelManualRow.objects.filter(active=True)
    accounts_rows = list(
        manual_rows.filter(section=ExcelManualRow.ACCOUNTS).order_by("sort_order", "id")
    )
    person_rows = list(
        manual_rows.filter(section=ExcelManualRow.PERSONS).order_by("sort_order", "id")
    )
    settings = {obj.key: obj for obj in ExcelManualSetting.objects.all()}
    takvin_debt = int(settings.get("takvin_debt").value or 0) if settings.get("takvin_debt") else 0
    digikala_base = (
        int(settings.get("digikala_receivable").value or 0)
        if settings.get("digikala_receivable")
        else 0
    )
    digikala_ledger = int(digikala_ledger_total())
    digikala_receivable = int(digikala_receivable_total())
    dia_gallery_receivable = int(dia_gallery_receivable_total())

    capital_account_rows = list(
        capital_accounts_queryset(manual_rows.filter(section=ExcelManualRow.ACCOUNTS))
    )
    accounts_total = (
        sum(int(row.amount or 0) for row in capital_account_rows)
        + sum(int(row.amount or 0) for row in person_rows)
        + dia_gallery_receivable
    )

    return {
        "accounts_rows": accounts_rows,
        "person_rows": person_rows,
        "accounts_total": accounts_total,
        "takvin_debt": takvin_debt,
        "digikala_receivable": digikala_receivable,
        "digikala_base_receivable": digikala_base,
        "digikala_ledger_total": digikala_ledger,
        "dia_gallery_receivable": dia_gallery_receivable,
    }


@login_required
def finance_home(request):
    # V102: Finance & Tools is a pure three-card hub. Account balances live only
    # inside the Accounts card/page; no account data is duplicated on the hub.
    return render(request, "core/finance_center_v97.html")


@login_required
def accounts(request):
    return render(request, "core/finance_accounts_v97.html", _finance_account_context())


@login_required
@require_POST
def accounts_action(request):
    # Reuse the exact report-side account mutation semantics, including:
    # - Digikala desired-total -> base conversion
    # - protected system-managed «خودم» row
    # - generic manual account/person row validation
    # Only the post-save redirect changes to the new Finance/Accounts page.
    report_manual_report_action(request)
    return redirect("finance_accounts")
