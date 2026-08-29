from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Sum
from django.urls import resolve

from core import material_report_v20 as v20
from core import material_report_v22 as v22
from core.material_report_v14 import _tailor_row
from core.models import Brand, MaterialReportBlock, MaterialReportOutputApplied, StockBalance


class Command(BaseCommand):
    help = "Transactional regression check for Novani two-way delivery sync and cut variance."

    def handle(self, *args, **options):
        if resolve("/material-report/").func.__module__ != "core.material_report_v22":
            raise CommandError("material-report route is not using v22")

        rate = int(v20._dozen_wage())
        if rate != 110000:
            raise CommandError(f"dozen wage must be 110000, found {rate}")

        novani = Brand.objects.get(name="Novani")
        darma = Brand.objects.get(name="دارما")
        novani_before = int(StockBalance.objects.filter(brand=novani).aggregate(v=Sum("qty"))["v"] or 0)
        darma_before = int(StockBalance.objects.filter(brand=darma).aggregate(v=Sum("qty"))["v"] or 0)
        tailor_obj = _tailor_row(create=False)
        tailor_before = int(tailor_obj.amount or 0) if tailor_obj else 0

        with transaction.atomic():
            block = MaterialReportBlock.objects.create(
                date=date.today(),
                title="__NOVANI_OUTPUT_V35_ROLLBACK_TEST__",
                brand=novani,
                input_data=v20._blank_input_data(),
                output_data=v20._blank_output_data_for_brand(novani),
            )
            block.input_data["black"]["cut"] = "20"
            block.output_data["black"]["s"] = "12"
            block.save(update_fields=["input_data", "output_data", "updated_at"])

            plus = v22._sync_novani_output(block)
            if plus["piece_delta"] != 12 or plus["wage_change"] != 110000:
                raise CommandError(f"positive sync mismatch: {plus}")

            novani_plus = int(StockBalance.objects.filter(brand=novani).aggregate(v=Sum("qty"))["v"] or 0)
            darma_plus = int(StockBalance.objects.filter(brand=darma).aggregate(v=Sum("qty"))["v"] or 0)
            tailor_plus_obj = _tailor_row(create=False)
            tailor_plus = int(tailor_plus_obj.amount or 0) if tailor_plus_obj else 0
            if novani_plus != novani_before + 12:
                raise CommandError("Novani positive stock delta failed")
            if darma_plus != darma_before:
                raise CommandError("Darma stock changed during Novani positive sync")
            if tailor_plus != tailor_before - 110000:
                raise CommandError("tailor wage was not deducted from delivered pieces")

            view = v22._view_block_v35(block)
            black = next(x for x in view["output_rows"] if x["model_key"] == "black")
            if black["cut_total"] != 20 or black["total"] != 12 or black["cut_diff"] != -8:
                raise CommandError(f"cut variance mismatch: {black}")

            # Clearing an already-applied delivery must remove exactly that stock and return its wage.
            block.output_data["black"]["s"] = ""
            block.save(update_fields=["output_data", "updated_at"])
            v22._validate_output_editable(block)
            minus = v22._sync_novani_output(block)
            if minus["piece_delta"] != -12 or minus["wage_change"] != -110000:
                raise CommandError(f"negative sync mismatch: {minus}")

            novani_zero = int(StockBalance.objects.filter(brand=novani).aggregate(v=Sum("qty"))["v"] or 0)
            tailor_zero_obj = _tailor_row(create=False)
            tailor_zero = int(tailor_zero_obj.amount or 0) if tailor_zero_obj else 0
            if novani_zero != novani_before or tailor_zero != tailor_before:
                raise CommandError("Novani negative sync did not restore stock/wage exactly")

            # Darma must keep the old positive-only safety rule.
            darma_block = MaterialReportBlock.objects.create(
                date=date.today(),
                title="__DARMA_FLOOR_V35_ROLLBACK_TEST__",
                brand=darma,
                input_data=v20._blank_input_data(),
                output_data=v20._blank_output_data_for_brand(darma),
            )
            MaterialReportOutputApplied.objects.create(
                block=darma_block,
                model_key="black",
                size_key="m",
                quantity=1,
            )
            try:
                v22._validate_output_editable(darma_block)
            except ValueError:
                pass
            else:
                raise CommandError("Darma reduction floor was accidentally removed")

            transaction.set_rollback(True)

        novani_after = int(StockBalance.objects.filter(brand=novani).aggregate(v=Sum("qty"))["v"] or 0)
        darma_after = int(StockBalance.objects.filter(brand=darma).aggregate(v=Sum("qty"))["v"] or 0)
        tailor_after_obj = _tailor_row(create=False)
        tailor_after = int(tailor_after_obj.amount or 0) if tailor_after_obj else 0
        if (novani_after, darma_after, tailor_after) != (novani_before, darma_before, tailor_before):
            raise CommandError("rollback regression test left business data changed")

        self.stdout.write("NOVANI OUTPUT V35 CHECK OK")
        self.stdout.write("Novani: applied delivery can be reduced/cleared and stock+wage reverse exactly")
        self.stdout.write("Darma: reduction safety unchanged")
        self.stdout.write("Cut variance: cut=20 / delivered=12 -> shortage=8")
        self.stdout.write("Dozen wage: 110000 per 12 pieces")
