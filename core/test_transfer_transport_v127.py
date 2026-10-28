"""V127 isolated tests: stock transfer transport, auth/CSRF and atomic response."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from core.models import (
    Brand, Color, InventoryMovement, Size, StockBalance,
    StockLocation, StockTransfer,
)


class TransferJsonTransportV127Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="v127-operator", password="v127-test-only-password"
        )
        cls.brand = Brand.objects.create(name="دارما")
        cls.color = Color.objects.create(name="V127 temporary black", active=True)
        cls.size = Size.objects.create(name="M", sort_order=1)
        cls.home = StockLocation.objects.create(key=StockLocation.HOME, title="خانه")
        cls.warehouse = StockLocation.objects.create(
            key=StockLocation.KHORSHID, title="خورشید"
        )
        StockBalance.objects.create(
            brand=cls.brand, color=cls.color, size=cls.size,
            location=cls.home, qty=3
        )
        StockBalance.objects.create(
            brand=cls.brand, color=cls.color, size=cls.size,
            location=cls.warehouse, qty=12
        )

    def setUp(self):
        self.url = reverse("inventory_transfer_direction_v123")
        self.data = {
            "date": "1405/08/06",
            "brand": self.brand.pk,
            "size": self.size.pk,
            "direction": "warehouse_to_home",
            f"qty_{self.color.pk}": "4",
        }
        self.ajax = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest",
                     "HTTP_ACCEPT": "application/json"}

    def _balances(self):
        return list(StockBalance.objects.filter(
            brand=self.brand, size=self.size, color=self.color
        ).order_by("location__key").values_list("location__key", "qty"))

    def test_expired_login_never_redirects_ajax_to_html(self):
        response = Client().post(self.url, self.data, **self.ajax)
        self.assertEqual(response.status_code, 401)
        self.assertIn("application/json", response["Content-Type"])
        self.assertEqual(response.json()["code"], "authentication_required")
        self.assertEqual(StockTransfer.objects.count(), 0)

    def test_expired_csrf_never_responds_html_to_ajax(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.post(self.url, self.data, **self.ajax)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "csrf_failed")
        self.assertEqual(StockTransfer.objects.count(), 0)

    def test_non_ajax_login_behavior_preserved(self):
        response = Client().post(self.url, self.data)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_success_keeps_all_real_stock_and_movement_ledgers_consistent(self):
        client = Client()
        client.force_login(self.user)
        before = self._balances()
        response = client.post(self.url, self.data, **self.ajax)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["transfer_ids"]), 1)
        self.assertEqual(StockTransfer.objects.count(), 1)
        self.assertEqual(InventoryMovement.objects.filter(
            movement_type=InventoryMovement.TRANSFER
        ).count(), 2)
        after = dict(self._balances())
        self.assertEqual(after[StockLocation.HOME], 7)
        self.assertEqual(after[StockLocation.KHORSHID], 8)
        self.assertEqual(sum(qty for _, qty in before), sum(after.values()))
        self.assertEqual(
            result["stock_snapshot"][f"{self.brand.pk}:{self.size.pk}:{self.color.pk}"]["total"],
            15,
        )

    def test_snapshot_failure_rolls_back_transfer_and_both_stock_movements(self):
        client = Client()
        client.force_login(self.user)
        before = self._balances()
        with patch(
            "core.inventory_transfer_v123._stock_snapshot_for_operations",
            side_effect=RuntimeError("synthetic snapshot error"),
        ):
            response = client.post(self.url, self.data, **self.ajax)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])
        self.assertEqual(self._balances(), before)
        self.assertEqual(StockTransfer.objects.count(), 0)
        self.assertEqual(InventoryMovement.objects.count(), 0)

    def test_short_source_rejects_entire_batch_without_writes(self):
        client = Client()
        client.force_login(self.user)
        before = self._balances()
        excessive = {**self.data, f"qty_{self.color.pk}": "13"}
        response = client.post(self.url, excessive, **self.ajax)
        self.assertEqual(response.status_code, 400)
        self.assertIn("کافی نیست", response.json()["message"])
        self.assertEqual(self._balances(), before)
        self.assertEqual(StockTransfer.objects.count(), 0)
