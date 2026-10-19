"""V125 safe stock-transfer AJAX, replay and unknown-response tests."""
from uuid import uuid4
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Brand, Color, Size, StockBalance, StockLocation, StockTransfer, InventoryMovement


class TransferJsonV125Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user("transfer-v125", password="test-only")
        cls.brand = Brand.objects.create(name="دارما", active=True)
        cls.color = Color.objects.create(name="صورتی", active=True)
        cls.size = Size.objects.create(name="M")
        cls.home = StockLocation.objects.create(key=StockLocation.HOME, title="خانه")
        cls.warehouse = StockLocation.objects.create(key=StockLocation.KHORSHID, title="انبار")
        StockBalance.objects.create(
            brand=cls.brand, color=cls.color, size=cls.size, location=cls.home, qty=10
        )
        StockBalance.objects.create(
            brand=cls.brand, color=cls.color, size=cls.size, location=cls.warehouse, qty=20
        )
        cls.url = reverse("inventory_transfer_direction_v123")

    def setUp(self):
        self.client.force_login(self.user)
        self.request_token = str(uuid4())

    def data(self, qty=3, token=None):
        return {
            "brand": str(self.brand.pk), "size": str(self.size.pk),
            "direction": "home_to_warehouse", "date": "1405/07/27",
            f"qty_{self.color.pk}": str(qty),
            "request_token": self.request_token if token is None else token,
        }

    def post(self, qty=3, token=None):
        return self.client.post(
            self.url, self.data(qty, token),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )

    def balances(self):
        return (
            StockBalance.objects.get(
                brand=self.brand, size=self.size, color=self.color, location=self.home
            ).qty,
            StockBalance.objects.get(
                brand=self.brand, size=self.size, color=self.color, location=self.warehouse
            ).qty,
        )

    def test_probe_is_json_and_never_changes_stock(self):
        res = self.client.get(
            self.url, HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json"
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "application/json")
        self.assertEqual(res.json()["version"], "v125")
        self.assertFalse(res.json()["found"])
        self.assertEqual(self.balances(), (10, 20))
        self.assertFalse(StockTransfer.objects.exists())

    def test_transfer_then_same_token_never_double_applies(self):
        first = self.post()
        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.json()["ok"])
        self.assertFalse(first.json()["replayed"])
        self.assertEqual(self.balances(), (7, 23))
        self.assertEqual(StockTransfer.objects.count(), 1)
        self.assertEqual(InventoryMovement.objects.count(), 2)
        second = self.post()
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.json()["ok"])
        self.assertTrue(second.json()["replayed"])
        self.assertEqual(second.json()["transfer_ids"], first.json()["transfer_ids"])
        self.assertEqual(self.balances(), (7, 23))
        self.assertEqual(StockTransfer.objects.count(), 1)
        self.assertEqual(InventoryMovement.objects.count(), 2)

    def test_status_probe_can_confirm_prior_committed_transfer(self):
        first = self.post()
        self.assertEqual(first.status_code, 200)
        status = self.client.get(
            self.url, {"request_token": self.request_token},
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(status.status_code, 200)
        self.assertTrue(status.json()["found"])
        self.assertTrue(status.json()["result"]["applied"])
        self.assertEqual(status.json()["result"]["transfer_ids"], first.json()["transfer_ids"])
        self.assertEqual(status.json()["stock_snapshot"][
            f"{self.brand.pk}:{self.size.pk}:{self.color.pk}"
        ]["home"], 7)
        self.assertEqual(self.balances(), (7, 23))

    def test_token_reused_with_different_amount_does_not_change_inventory(self):
        self.assertEqual(self.post().status_code, 200)
        changed = self.post(qty=7)
        self.assertEqual(changed.status_code, 400)
        self.assertEqual(changed["Content-Type"], "application/json")
        self.assertIn("متفاوتی", changed.json()["message"])
        self.assertEqual(self.balances(), (7, 23))
        self.assertEqual(StockTransfer.objects.count(), 1)

    def test_invalid_token_and_insufficient_stock_are_json_errors(self):
        invalid = self.post(token="not-a-uuid")
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid["Content-Type"], "application/json")
        shortage = self.post(qty=100)
        self.assertEqual(shortage.status_code, 400)
        self.assertEqual(shortage["Content-Type"], "application/json")
        self.assertEqual(self.balances(), (10, 20))
        self.assertFalse(StockTransfer.objects.exists())

    def test_expired_session_returns_json_401_instead_of_login_html(self):
        self.client.logout()
        r = self.client.post(
            self.url, self.data(), HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json"
        )
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r["Content-Type"], "application/json")
        self.assertEqual(r.json()["code"], "auth_required")
        self.assertEqual(self.balances(), (10, 20))

    @patch("core.inventory_transfer_v123._stock_snapshot_for_operations",
           side_effect=RuntimeError("read-only snapshot failed"))
    def test_success_is_json_even_when_snapshot_throws_after_commit(self, mock_snapshot):
        first = self.post()
        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.json()["ok"])
        self.assertIsNone(first.json()["stock_snapshot"])
        self.assertTrue(first.json()["refresh_needed"])
        self.assertEqual(self.balances(), (7, 23))
        status = self.client.get(
            self.url, {"request_token": self.request_token}, HTTP_ACCEPT="application/json"
        )
        self.assertEqual(status.status_code, 200)
        self.assertTrue(status.json()["found"])
        self.assertEqual(self.balances(), (7, 23))
