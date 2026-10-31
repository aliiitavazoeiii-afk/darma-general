"""Read-only Takvin account snapshot; never recreates deleted payments or changes money."""
from pathlib import Path
from django.core.management.base import BaseCommand
from django.db.models import Sum
from django.utils import timezone
from core.models import BusinessPayment, ExcelManualSetting, ExcelManualRow, TakvinPurchase


class Command(BaseCommand):
    help = "Audit Takvin debt and payment trail without changing production records"

    def handle(self, *args, **options):
        qs = ExcelManualSetting.objects.filter(key="takvin_debt")
        if not qs.exists():
            raise RuntimeError("takvin_debt setting absent; no silent defaults")
        setting = qs.get()
        balance = int(setting.value or 0)
        self.stdout.write("=== TAKVIN READ-ONLY FINANCE AUDIT ===")
        self.stdout.write(f"TAKVIN_SIGNED_BALANCE_TOMAN={balance}")
        self.stdout.write(f"TAKVIN_BALANCE_MEANING={'supplier_debt' if balance>0 else 'credit_from_supplier' if balance<0 else 'settled'}")
        self.stdout.write(f"TAKVIN_UPDATED_AT={timezone.localtime(setting.updated_at).isoformat()}")
        payments = BusinessPayment.objects.filter(payee="takvin")
        self.stdout.write(f"TAKVIN_ACTIVE_PAYMENTS_COUNT={payments.count()}")
        self.stdout.write(f"TAKVIN_ACTIVE_PAYMENTS_TOTAL={int(payments.aggregate(v=Sum('amount'))['v'] or 0)}")
        for p in payments.order_by("-id")[:15]:
            self.stdout.write(f"PAYMENT id={p.id} date={p.date} amount={p.amount} source={p.source_account}")
        self.stdout.write(f"TAKVIN_PURCHASE_RECORDS={TakvinPurchase.objects.count()}")
        self.stdout.write(f"TAKVIN_PURCHASE_TOTAL={int(TakvinPurchase.objects.aggregate(v=Sum('total_cost'))['v'] or 0)}")
        for p in TakvinPurchase.objects.order_by("-id")[:6]:
            self.stdout.write(f"PURCHASE id={p.id} date={p.date} total_cost={p.total_cost}")
        for row in ExcelManualRow.objects.filter(section=ExcelManualRow.ACCOUNTS, active=True).order_by("id"):
            if "ملت" in row.title or "مفید" in row.title:
                self.stdout.write(f"BANK_ACCOUNT id={row.id} title={row.title} balance={row.amount}")
        self.stdout.write("NOTE: Deleted payment details and exact pre-payment balance cannot be inferred from the current mutable setting alone.")
        self.stdout.write("NOTE: Inspect SQL backups taken BEFORE the first overpayment, plus bank transaction evidence, before any one-time repair.")
        self.stdout.write(self.style.SUCCESS("SUCCESS: TAKVIN READ-ONLY AUDIT; NO DATABASE WRITES"))
