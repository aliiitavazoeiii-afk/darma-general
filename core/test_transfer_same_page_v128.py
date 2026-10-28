"""V128: test canonical same-page transfer POST on isolated test DB.

Reuse ALL V127 business-ledger invariants but target the existing GET/POST
inventory operations URL. This catches 404 routing regressions without a
production POST, while the V123 dedicated URL stays backward-compatible.
"""
from pathlib import Path

from django.conf import settings
from django.test import Client, override_settings
from django.urls import resolve, reverse

from core import inventory_operations_v16, inventory_transfer_v123
from core.models import StockTransfer
from core.test_transfer_transport_v127 import TransferJsonTransportV127Tests


class SamePageTransferV128Tests(TransferJsonTransportV127Tests):
    def setUp(self):
        super().setUp()
        self.url = reverse("inventory_operations")
        self.data["action"] = "transfer"

    def test_same_route_serves_get_and_ajax_transfer_post(self):
        self.assertEqual(self.url, "/inventory/operations/")
        self.assertIs(resolve(self.url).func, inventory_operations_v16.inventory_operations)
        client = Client()
        client.force_login(self.user)
        with override_settings(STORAGES={
            "staticfiles": {
                "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
            },
        }):
            get_response = client.get(self.url)
        self.assertEqual(get_response.status_code, 200)
        html = get_response.content.decode("utf-8")
        self.assertIn('id="stock-transfer-form"', html)
        self.assertIn('action="/inventory/operations/"', html)
        self.assertNotIn('action="/inventory/operations/transfer-direction/"', html)
        post_response = client.post(self.url, self.data, **self.ajax)
        self.assertEqual(post_response.status_code, 200)
        self.assertTrue(post_response.json()["ok"])
        self.assertEqual(StockTransfer.objects.count(), 1)

    def test_old_explicit_route_stays_backward_compatible(self):
        self.assertIs(
            resolve(reverse("inventory_transfer_direction_v123")).func,
            inventory_transfer_v123.inventory_transfer_direction,
        )
        client = Client()
        client.force_login(self.user)
        result = client.post(
            reverse("inventory_transfer_direction_v123"), self.data,
            **self.ajax
        )
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.json()["ok"])

    def test_template_canonical_route_guard(self):
        page = (
            Path(settings.BASE_DIR) / "templates/core/inventory_operations.html"
        ).read_text(encoding="utf-8")
        self.assertIn(
            'action="{% url \'inventory_operations\' %}"', page
        )
        self.assertIn("new FormData(transferForm)", page)
