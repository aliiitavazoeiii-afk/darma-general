"""Read-only fabric roll audit, with source sheet codes for each Darma color."""
from django.core.management.base import BaseCommand
from core import material_report_v92 as report
from core.models import MaterialReportBlock


class Command(BaseCommand):
    help = "Audit registered fabric codes vs uncoded material sheets; never change stock."

    def handle(self, *args, **kwargs):
        blocks = list(
            MaterialReportBlock.objects.select_related("brand")
            .prefetch_related("output_applications").all()
        )
        rows = report._summarize_open_base_colors(blocks)
        for result in rows:
            codes = {}
            missing = []
            for block in blocks:
                if block.brand.name != "دارما":
                    continue
                values = (block.input_data or {}).get(result["key"]) or {}
                code = str(values.get("fabric_code") or "").strip()
                cut = max(0, report.v23.v20._int(values.get("cut")))
                weight = max(report._decimal(values.get("weight")), report.Decimal("0"))
                if code:
                    codes.setdefault(code, []).append(block.id)
                elif cut > 0 or weight > 0:
                    missing.append(block.id)
            if result["roll_count"] != len(codes):
                raise RuntimeError(f"Count mismatch for {result['key']}")
            self.stdout.write(
                f"{result['label']} | unique_registered_codes={len(codes)} "
                f"| missing_code_sheets={len(missing)} "
                f"| open_cut={result['expected']} "
                f"| applied_output={result['delivered']} "
                f"| pending_output={result['pending']}"
            )
            self.stdout.write("  coded_sheets="+repr(codes))
            self.stdout.write("  uncoded_sheet_ids="+repr(missing))
        self.stdout.write(self.style.SUCCESS("SUCCESS: FABRIC ROLL COUNT AUDIT V116 PASSED"))
