from django.core.management.base import BaseCommand, CommandError
from django.urls import resolve, reverse

from core.finance_excel_v9 import digikala_receivable_total
from core.models import Account, BusinessPayment, DigikalaSettlement


class Command(BaseCommand):
    help = "Verify automatic Digikala receivable and payments/receipts v9 routes."

    def handle(self, *args, **options):
        errors = []
        checks = {
            "report": "core.report_v9",
            "manual_report_action": "core.report_v9",
            "payments": "core.business_tools_v9",
            "payment_add": "core.business_tools_v9",
            "receipt_add": "core.business_tools_v9",
            "calculator": "core.business_tools_v9",
        }
        route_args = {"receipt_add": [], "payment_add": []}
        for name, module in checks.items():
            try:
                url = reverse(name, args=route_args.get(name, []))
                actual = resolve(url).func.__module__
                if actual != module:
                    errors.append(f"{name} points to {actual}, expected {module}")
                else:
                    self.stdout.write(f"route OK: {name} -> {actual}")
            except Exception as exc:
                errors.append(f"route {name}: {exc}")

        try:
            Account.objects.get_or_create(key=Account.DIGIKALA, defaults={"title": "دیجی‌کالا", "opening_balance": 0})
            BusinessPayment.objects.count()
            DigikalaSettlement.objects.count()
            digikala_receivable_total()
            self.stdout.write("finance models OK")
        except Exception as exc:
            errors.append(f"finance models: {exc}")

        if errors:
            for error in errors:
                self.stderr.write(self.style.ERROR(error))
            raise CommandError("Finance flow v9 preflight failed")

        self.stdout.write(self.style.SUCCESS("FINANCE FLOW V9 OK"))
