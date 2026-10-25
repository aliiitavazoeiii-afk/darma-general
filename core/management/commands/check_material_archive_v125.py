"""Read-only V125 regression and live archived Jalali month material status."""
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.template.loader import get_template

from core import material_report_v92 as report
from core.management.commands.check_material_net_v122 import sheet
from core.models import MaterialReportBlock


def synthetic_check():
    # Explicitly compare Mehr 1405 with current Aban 1405.
    aban = report._jalali_month_context(date(2026, 10, 25))
    mehr = report._jalali_month_context(date(2026, 10, 12))
    assert aban["key"] == "1405/08" and mehr["key"] == "1405/07"
    first = sheet(101, date(2026, 10, 10), cut=750,
                  delivered=998, applied=900, raw_applied=False)
    second = sheet(102, date(2026, 10, 11), cut=750,
                   delivered=540, applied=333, raw_applied=False)
    # Completed raw fabric does NOT appear in the 'unapplied materials' cards;
    # its UNDELIVERED output must still appear under full-month debts.
    white_due = sheet(103, date(2026, 10, 12), color="white",
                      cut=120, delivered=40, applied=40, raw_applied=True)
    # A fully settled third color should not create a spurious deficit.
    cream_done = sheet(104, date(2026, 10, 13), color="cream",
                       cut=80, delivered=80, applied=80, raw_applied=True)
    # Aban production must NEVER inflate Mehr and vice versa.
    aban_own = sheet(105, date(2026, 10, 25), color="pink",
                     cut=3000, delivered=0, applied=0, raw_applied=False)
    old_shahrivar = sheet(106, date(2026, 9, 10), color="pink",
                          cut=5000, delivered=0, applied=0, raw_applied=False)
    future = sheet(107, date(2026, 12, 1), color="pink",
                   cut=9000, delivered=0, applied=0, raw_applied=False)
    objects = [first, second, white_due, cream_done, aban_own, old_shahrivar, future]

    current = [row for row in objects if aban["start"] <= row.date < aban["next"]]
    current_summary, current_colors, _ = report._current_unapplied_material_metrics(current)
    if current_summary["minimum_delivery"] != 3000 or current_colors["pink"]["expected"] != 3000:
        raise RuntimeError("Current Aban report was mixed with prior months")

    archived = report._past_month_dashboard_reports(objects, aban)
    by_month = {item["key"]: item for item in archived}
    if set(by_month) != {"1405/07", "1405/06"}:
        raise RuntimeError(f"Incorrect archives: {list(by_month)}")
    mehr_report = by_month["1405/07"]
    summary = mehr_report["summary"]
    if (
        summary["minimum_delivery"], summary["delivered"],
        summary["applied"], summary["pending"], summary["surplus"],
        summary["roll_count"],
    ) != (1500, 1538, 1233, 0, 38, 2):
        raise RuntimeError(f"Mehr unapplied materials changed: {summary}")
    pink = next(x for x in mehr_report["color_progress"] if x["key"] == "pink")
    if (pink["expected"], pink["delivered"], pink["pending"], pink["surplus"]) != (
        1500, 1538, 0, 38
    ):
        raise RuntimeError(f"Mehr pink receipt net incorrect: {pink}")

    delivery = mehr_report["delivery"]
    by_color = {(item["brand"], item["key"]): item for item in delivery["rows"]}
    if (delivery["expected"], delivery["delivered"], delivery["applied"],
            delivery["pending"], delivery["surplus"],
            delivery["awaiting_stock_apply"]) != (1700, 1658, 1353, 80, 38, 305):
        raise RuntimeError(f"Mehr whole-month independent color debts incorrect: {delivery}")
    if by_color[("دارما", "white")]["pending"] != 80:
        raise RuntimeError("White stock-applied materials improperly hid unreceived sewing output")
    if by_color[("دارما", "pink")]["surplus"] != 38:
        raise RuntimeError("Pink roll surpluses not netted before clamp")
    if by_color[("دارما", "cream")]["pending"]:
        raise RuntimeError("Completed cream wrongly marked pending")
    if by_month["1405/06"]["delivery"]["pending"] != 5000:
        raise RuntimeError("Shahrivar incorrectly mixed with Mehr")
    if mehr_report["sheet_count"] != 4 or by_month["1405/06"]["sheet_count"] != 1:
        raise RuntimeError("Archive grouping not by original Jalali sheet month")
    # After a late delivery is saved against Mehr, recomputing the report updates
    # the numbers but MUST NOT create any carryover in current Aban.
    white_due.output_data["white"]["m"] = "120"
    updated = {x["key"]: x for x in report._past_month_dashboard_reports(objects, aban)}
    if updated["1405/07"]["delivery"]["pending"] != 0:
        raise RuntimeError("Prior month archive did not refresh after additional delivery")
    if report._current_unapplied_material_metrics(current)[0]["minimum_delivery"] != 3000:
        raise RuntimeError("Updating old sheets polluted current month")


class Command(BaseCommand):
    help = "V125 verify click-to-open archive month KPIs plus full delivery debts; no data writes."

    def handle(self, *args, **kwargs):
        synthetic_check()
        root = Path(settings.BASE_DIR)
        html = (root / "templates/core/material_report_v92.html").read_text("utf-8")
        partial = (root / "templates/core/_material_month_archive_report_v125.html").read_text("utf-8")
        for required in (
            "materialArchiveReports", "archiveReportNodes", "reportNode.cloneNode(true)",
            "archive.append(summary, body)", "keyToNumber(key) >= currentNumber",
        ):
            if required not in html:
                raise RuntimeError(f"Archive closed/open UI missing marker: {required}")
        for required in (
            "archive.summary.roll_count", "archive.color_progress", "archive.delivery.rows",
            "archive.delivery.pending", "row.awaiting_stock_apply",
        ):
            if required not in partial:
                raise RuntimeError(f"Archive summary or receipt details missing: {required}")
        get_template("core/material_report_v92.html")
        get_template("core/_material_month_archive_report_v125.html")
        current = report._jalali_month_context()
        blocks = list(
            MaterialReportBlock.objects.select_related("brand").prefetch_related(
                "stock_consumptions", "output_applications"
            )
        )
        reports = report._past_month_dashboard_reports(blocks, current)
        self.stdout.write(f"CURRENT_MONTH={current['label']} ARCHIVED_MONTHS={len(reports)}")
        for item in reports[:24]:
            delivered = item["delivery"]
            summary = item["summary"]
            self.stdout.write(
                f"ARCHIVE={item['label']} SHEETS={item['sheet_count']} "
                f"UNAPPLIED_ROLLS={summary['roll_count']} "
                f"UNAPPLIED_CUT={summary['minimum_delivery']} "
                f"UNAPPLIED_PENDING={summary['pending']} "
                f"ALL_PENDING={delivered['pending']} "
                f"ALL_DELIVERED={delivered['delivered']} "
                f"ALL_STOCK_UNAPPLIED={delivered['awaiting_stock_apply']}"
            )
        self.stdout.write("DATA_WRITES=ZERO; CURRENT_MONTH_ISOLATED=True; NO_HISTORICAL_SNAPSHOT")
        self.stdout.write(self.style.SUCCESS(
            "SUCCESS: V125 ARCHIVED JALALI MONTH DASHBOARDS PASS"
        ))
