"""V156: seven independent read-only screens + data integrity guards."""
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from core.models import (
    Account, AccountEntry, Brand, Color, ProductCode, ProductSize,
    SaleDay, SaleLine, Size, StockBalance, StockLocation,
    ExcelManualSetting,
)


class ControlRoomReadOnlyV156Tests(TransactionTestCase):
    # TransactionTestCase keeps no outer test transaction: PostgreSQL can
    # enforce SET TRANSACTION READ ONLY at the start of every actual request.
    reset_sequences = False

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="control-room-v156", password="not-a-live-secret",
        )
        self.client = Client()
        self.client.force_login(self.user)
        self.brand = Brand.objects.create(name="دارما")
        self.size = Size.objects.create(name="M", sort_order=1)
        self.color = Color.objects.create(name="مشکی")
        self.home = StockLocation.objects.create(key="home", title="خانه")
        StockLocation.objects.create(key="khorshid", title="خورشید")
        self.product = ProductCode.objects.create(
            brand=self.brand, code="TEST-ROOM", title="test", pack_qty=3,
        )
        self.ps = ProductSize.objects.create(
            product=self.product, size=self.size,
            default_sale_price=480000, unit_cost=70000,
        )
        day = SaleDay.objects.create(date=timezone.localdate())
        self.line = SaleLine.objects.create(
            day=day, product_size=self.ps, quantity=2, sale_price=480000,
        )
        self.balance = StockBalance.objects.create(
            brand=self.brand, size=self.size, color=self.color,
            location=self.home, qty=12,
        )
        self.account = Account.objects.create(
            key=Account.DIGIKALA, title="دیجی‌کالا", opening_balance=0,
        )
        self.setting = ExcelManualSetting.objects.create(
            key="digikala_receivable", label="طلب پایه", value=500,
        )

    def _ledger(self):
        return {
            "sale": list(SaleLine.objects.values_list(
                "id", "quantity", "sale_price", "inventory_applied_quantity",
            )),
            "stock": list(StockBalance.objects.values_list("id", "qty")),
            "accounts": list(AccountEntry.objects.values_list("id", "delta")),
            "settings": list(ExcelManualSetting.objects.values_list("key", "value")),
        }

    def test_all_tabs_return_200_and_execute_no_write_sql(self):
        before = self._ledger()
        url = reverse("control_room")
        for tab in ["overview", "audit", "inventory", "profit",
                    "cash", "production", "integrity"]:
            with self.subTest(tab=tab):
                with CaptureQueriesContext(connection) as queries:
                    response = self.client.get(url, {"tab": tab})
                self.assertEqual(response.status_code, 200, response.content[:500])
                self.assertContains(response, "READ ONLY")
                self.assertContains(response, "INTELLIGENCE ROOM")
                self.assertContains(response, "بازگشت به پنل اصلی")
                sql_texts = [q["sql"].lstrip().upper() for q in queries]
                self.assertFalse([
                    q for q in sql_texts if q.startswith((
                        "INSERT ", "UPDATE ", "DELETE ", "CREATE ",
                        "DROP ", "ALTER ", "TRUNCATE ",
                    ))
                ])
                if connection.vendor == "postgresql":
                    self.assertTrue(any(
                        "SET TRANSACTION READ ONLY" in q
                        for q in sql_texts
                    ))
                self.assertEqual(before, self._ledger())

    def test_post_and_mutation_methods_rejected(self):
        url = reverse("control_room")
        before = self._ledger()
        self.assertEqual(self.client.post(url).status_code, 405)
        self.assertEqual(self.client.put(url).status_code, 405)
        self.assertEqual(self.client.delete(url).status_code, 405)
        self.assertEqual(before, self._ledger())

    def test_requires_authentication_and_does_not_change_other_routes(self):
        anon = Client()
        response = anon.get(reverse("control_room"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])
        self.assertEqual(reverse("dashboard"), "/")
        self.assertEqual(reverse("report"), "/report/")
        response = self.client.get(reverse("control_room"), {"tab": "unknown"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "اتاق کنترل کسب‌وکار")

    def test_audit_flags_missing_snapshot_and_ledger_without_fixing(self):
        response = self.client.get(reverse("control_room"), {"tab": "audit"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "فروش فاقد Snapshot")
        self.assertContains(response, "اختلاف سند طلب دیجی‌کالا")
        self.assertFalse(AccountEntry.objects.exists())
        from core.models import SaleSnapshot
        self.assertEqual(SaleSnapshot.objects.count(), 0)

    def test_stock_negative_is_visible_but_not_modified(self):
        self.balance.qty = -3
        self.balance.save(update_fields=["qty"])
        response = self.client.get(reverse("control_room"), {"tab": "inventory"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "دارما · مشکی · M")
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.qty, -3)
