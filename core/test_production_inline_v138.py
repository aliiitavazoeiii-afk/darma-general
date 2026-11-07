"""V138: AJAX saves must never redirect; original inventory and wage handlers remain authoritative."""
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import resolve, reverse

from core import production_inline_v138 as inline, material_report_ui_v131 as ui
from core import material_report_v23 as posting
from core.models import (
    AppSetting, Brand, Color, InventoryMovement, MaterialReportBlock,
    MaterialReportOutputApplied, MaterialReportOutputLocation, RawMaterialStock,
    Size, StockBalance, StockLocation,
)


class ProductionInlineV138Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="v138-test", password="v138-test-password"
        )
        self.client.force_login(self.user)
        self.brand = Brand.objects.create(name="دارما")
        self.color = Color.objects.create(name="صورتی")
        self.white = Color.objects.create(name="سفید")
        self.home = StockLocation.objects.create(key="home", title="خانه")
        self.khorshid = StockLocation.objects.create(key="khorshid", title="خورشید")
        Size.objects.bulk_create([
            Size(name=name, sort_order=i)
            for i, name in enumerate(("M", "L", "XL", "XXL", "3XL", "4XL"), start=1)
        ])
        AppSetting.objects.create(key="pedram_dozen_wage", label="مزد", value="110000")
        self.block = MaterialReportBlock.objects.create(
            date=date(2026, 10, 25), title="P8 + W1", brand=self.brand,
            input_data={
                "_meta": {"active_material_keys": list(posting.BASE_KEYS)},
                "pink": {"fabric_code": "P8", "weight": "20", "cut": "760",
                         "elastic16_key": "pink", "elastic16": "2.5",
                         "elastic25_key": "pink", "elastic25": "2.5"},
                "white": {"fabric_code": "W1", "weight": "21", "cut": "755"},
            },
            output_data={
                "pink": {"m": "0", "xl": "0"},
                "white": {"m": "0", "xl": "0"},
            },
        )

    def _payload(self, action, *, destination=None, pink_m=0, white_m=0):
        editor = ui._editor(self.block)
        values = {
            "date": editor["date_j"],
            "title": self.block.title,
            "brand": str(self.brand.pk),
            "note": self.block.note,
            "active_material_keys": editor["active_keys_csv"],
            "_inline_action": action,
        }
        for field in editor["hidden_fields"]:
            values[field["name"]] = field["value"]
        for field in editor["delivery_fields"]:
            values[field["name"]] = field["value"]
        for row in editor["rows"]:
            for field in row["fields"]:
                if not field["readonly"]:
                    values[field["name"]] = field["value"]
            for size in row["sizes"]:
                for part in size["parts"]:
                    values[part["name"]] = part["value"]
        values["out_pink_m_1"] = str(pink_m)
        values["out_white_m_1"] = str(white_m)
        if destination is not None:
            values["delivery_destination"] = destination
        return values

    def _post(self, payload):
        return self.client.post(
            reverse("material_block_inline", args=[self.block.pk]),
            data=payload, HTTP_X_REQUESTED_WITH="XMLHttpRequest", HTTP_ACCEPT="application/json",
        )

    def _qty(self, location):
        return int(StockBalance.objects.filter(
            brand=self.brand, color=self.color, size__name="M", location=location,
        ).values_list("qty", flat=True).first() or 0)

    def test_inline_route_exists_and_original_post_routes_unchanged(self):
        self.assertIs(resolve(reverse("material_block_inline", args=[1])).func,
                      inline.material_block_inline_action)
        self.assertIs(resolve(reverse("material_block_save", args=[1])).func,
                      posting.material_block_save)
        self.assertIs(resolve(reverse("material_block_apply_output", args=[1])).func,
                      posting.material_block_apply_output)
        self.assertIs(resolve(reverse("material_block_apply_color", args=[1])).func,
                      posting.material_block_apply_color)
        page = self.client.get(reverse("material_report"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'data-inline-url=')
        self.assertContains(page, '?v=138')
        js = (Path(settings.BASE_DIR) /
              "core/static/core/production_workspace_v131.js").read_text("utf-8")
        for marker in ("event.preventDefault()", "new FormData(form)",
                       "fetch(inlineUrl", "pendingInlineRequest",
                       "inlineUpdateRow", "dialog.close()", "visibleRows()"):
            self.assertIn(marker, js)
        # The new inline flow must never assign a URL or replace the editing DOM.
        inline_part = js.split("// V138: send save", 1)[1]
        self.assertNotIn("window.location", inline_part)
        self.assertNotIn("innerHTML", inline_part)
        self.assertNotIn("window.scrollTo", inline_part)

    def test_save_only_returns_json_no_redirect_and_no_inventory_mutation(self):
        before = (InventoryMovement.objects.count(), StockBalance.objects.count())
        response = self._post(self._payload("save", pink_m=28))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertNotIn("Location", response)
        payload = response.json()
        self.assertTrue(payload["ok"], payload)
        self.assertEqual(payload["action"], "save")
        self.assertEqual(payload["block_id"], self.block.pk)
        keys = {row["key"] for row in payload["rows"]}
        self.assertIn("pink", keys)
        self.assertIn("white", keys)
        pink = next(row for row in payload["rows"] if row["key"] == "pink")
        self.assertEqual(pink["entered"], 28)
        self.assertEqual(pink["applied"], 0)
        self.assertTrue(pink["dirty_stock"])
        self.assertEqual((InventoryMovement.objects.count(), StockBalance.objects.count()), before)
        self.block.refresh_from_db()
        self.assertEqual(int(self.block.output_data["pink"]["m"]), 28)
        self.assertEqual(self.block.input_data["white"]["fabric_code"], "W1")

    def test_apply_home_then_khorshid_updates_only_delta_and_wage_once(self):
        first = self._post(self._payload("apply-output", destination="home", pink_m=12))
        self.assertEqual(first.status_code, 200, first.content[:500])
        self.assertTrue(first.json()["ok"], first.json())
        pink = next(row for row in first.json()["rows"] if row["key"] == "pink")
        self.assertEqual(pink["entered"], 12)
        self.assertEqual(pink["applied"], 12)
        self.assertFalse(pink["dirty_stock"])
        self.assertFalse(first.json()["deletable"])
        self.assertEqual((self._qty(self.home), self._qty(self.khorshid)), (12, 0))
        self.assertEqual(InventoryMovement.objects.count(), 1)
        self.block.refresh_from_db()
        wage_first = self.block.delivery_wage

        repeated = self._post(self._payload("apply-output", destination="home", pink_m=12))
        self.assertEqual(repeated.status_code, 200, repeated.content[:500])
        self.assertEqual((self._qty(self.home), self._qty(self.khorshid)), (12, 0))
        self.assertEqual(InventoryMovement.objects.count(), 1)
        self.block.refresh_from_db()
        self.assertEqual(self.block.delivery_wage, wage_first)

        second = self._post(self._payload("apply-output", destination="khorshid", pink_m=18))
        self.assertEqual(second.status_code, 200, second.content[:500])
        self.assertTrue(second.json()["ok"], second.json())
        self.assertEqual((self._qty(self.home), self._qty(self.khorshid)), (12, 6))
        self.assertEqual(InventoryMovement.objects.count(), 2)
        self.assertEqual(
            MaterialReportOutputApplied.objects.get(block=self.block, model_key="pink",
                size_key="m").quantity, 18
        )
        self.assertEqual(
            MaterialReportOutputLocation.objects.filter(
                applied__block=self.block, applied__model_key="pink",
                applied__size_key="m").count(), 2
        )
        self.block.refresh_from_db()
        self.assertGreater(self.block.delivery_wage, wage_first)

    def test_invalid_warehouse_rolls_back_everything_and_shows_inline_error(self):
        resp = self._post(self._payload("apply-output", destination="moon", pink_m=31))
        self.assertEqual(resp.status_code, 422)
        self.assertFalse(resp.json()["ok"])
        self.assertIn("انبار", resp.json()["message"])
        self.block.refresh_from_db()
        self.assertEqual(InventoryMovement.objects.count(), 0)
        self.assertEqual(StockBalance.objects.count(), 0)
        self.assertEqual(int(self.block.output_data["pink"].get("m") or 0), 0)

    def test_reject_unknown_action_missing_ajax_header_and_unauthenticated_user(self):
        bad = self._post(self._payload("delete", pink_m=22))
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(InventoryMovement.objects.count(), 0)
        ordinary = self.client.post(reverse("material_block_inline", args=[self.block.pk]),
                                    self._payload("save", pink_m=24))
        self.assertEqual(ordinary.status_code, 400)
        self.client.logout()
        unauth = self._post(self._payload("save", pink_m=30))
        self.assertEqual(unauth.status_code, 302)
        self.block.refresh_from_db()
        self.assertEqual(int(self.block.output_data["pink"].get("m") or 0), 0)

    def test_legacy_save_still_returns_redirect_for_fallback(self):
        response = self.client.post(
            reverse("material_block_save", args=[self.block.pk]),
            self._payload("save", pink_m=11),
        )
        self.assertEqual(response.status_code, 302)
        self.block.refresh_from_db()
        self.assertEqual(int(self.block.output_data["pink"]["m"]), 11)
