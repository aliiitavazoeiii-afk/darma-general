"""V125 regression: no HTML login redirect for AJAX, no duplicate transfer on errors."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from core.models import Brand, Color, InventoryMovement, Size, StockBalance, StockLocation, StockTransfer


class AjaxTransferTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.brand = Brand.objects.create(name="دارما", active=True)
        cls.color = Color.objects.create(name="صورتی", active=True)
        cls.size = Size.objects.create(name="M")
        cls.home = StockLocation.objects.create(key="home", title="خانه")
        cls.warehouse = StockLocation.objects.create(key="khorshid", title="خورشید")
        StockBalance.objects.create(
            brand=cls.brand, color=cls.color, size=cls.size,
            location=cls.home, qty=10
        )
        StockBalance.objects.create(
            brand=cls.brand, color=cls.color, size=cls.size,
            location=cls.warehouse, qty=20
        )

    def _payload(self, direction="warehouse_to_home", qty=4):
        return {
            "date": "1405/08/02",
            "brand": str(self.brand.pk),
            "size": str(self.size.pk),
            "direction": direction,
            f"qty_{self.color.pk}": str(qty),
        }

    def _assert_balances(self, home, warehouse):
        a=StockBalance.objects.get(
            brand=self.brand, color=self.color, size=self.size, location=self.home
        )
        b=StockBalance.objects.get(
            brand=self.brand, color=self.color, size=self.size, location=self.warehouse
        )
        self.assertEqual((a.qty,b.qty,a.qty+b.qty),(home,warehouse,30))

    def test_logged_out_ajax_is_401_json_without_stock_change(self):
        res=self.client.post(
            reverse("inventory_transfer_direction_v123"),
            self._payload(),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(res.status_code,401)
        self.assertTrue(res["Content-Type"].startswith("application/json"))
        self.assertFalse(res.json()["ok"])
        self.assertEqual(res.json()["code"],"login_required")
        self.assertEqual(StockTransfer.objects.count(),0)
        self._assert_balances(10,20)

    def test_logged_out_standard_form_still_redirects_to_login(self):
        res=self.client.post(
            reverse("inventory_transfer_direction_v123"),self._payload()
        )
        self.assertEqual(res.status_code,302)
        self.assertIn("/login/",res["Location"])
        self.assertEqual(StockTransfer.objects.count(),0)

    def test_authenticated_ajax_warehouse_to_home_returns_json_and_moves_once(self):
        u=get_user_model().objects.create_user("stockajax",password="test-012345")
        self.client.force_login(u)
        res=self.client.post(
            reverse("inventory_transfer_direction_v123"),
            self._payload(),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(res.status_code,200,res.content[:300])
        self.assertTrue(res["Content-Type"].startswith("application/json"))
        data=res.json()
        self.assertTrue(data["ok"])
        self.assertEqual(len(data["transfer_ids"]),1)
        self.assertEqual(StockTransfer.objects.count(),1)
        self.assertEqual(InventoryMovement.objects.count(),2)
        self._assert_balances(14,16)

    def test_authenticated_ajax_home_to_warehouse_also_returns_json(self):
        u=get_user_model().objects.create_user("stockajax",password="test-012345")
        self.client.force_login(u)
        res=self.client.post(
            reverse("inventory_transfer_direction_v123"),
            self._payload(direction="home_to_warehouse",qty=4),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(res.status_code,200)
        self.assertTrue(res.json()["ok"])
        self._assert_balances(6,24)

    def test_shortage_rejected_as_json_with_no_stock_change(self):
        u=get_user_model().objects.create_user("stockajax",password="test-012345")
        self.client.force_login(u)
        res=self.client.post(
            reverse("inventory_transfer_direction_v123"),
            self._payload(qty=25),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(res.status_code,400)
        self.assertEqual(res.json()["code"],"transfer_rejected")
        self.assertFalse(res.json()["ok"])
        self.assertEqual(StockTransfer.objects.count(),0)
        self._assert_balances(10,20)

    def test_expired_csrf_returns_403_html_without_stock_change(self):
        u=get_user_model().objects.create_user("stockajax",password="test-012345")
        client=Client(enforce_csrf_checks=True)
        client.force_login(u)
        res=client.post(
            reverse("inventory_transfer_direction_v123"),
            self._payload(),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(res.status_code,403)
        self.assertEqual(StockTransfer.objects.count(),0)
        self._assert_balances(10,20)
