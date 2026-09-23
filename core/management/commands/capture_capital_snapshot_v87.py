"""Capture today's capital or import an audited observation from an isolated SQL backup.

Never sets old dates from the current database. Historical backfill requires an
external trusted backup and its SHA-256 fingerprint.
"""
import hashlib
import json
import re
import sys
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, connection
from django.utils import timezone

from core.capital_history_v87 import capture_current_capital_payload, validate_capital_payload
from core.models import CapitalSnapshot


def _read_consistent_current():
    # Snapshot before storage, with one database-wide MVCC view of every account
    # and inventory row, rather than mixing values from concurrent transactions.
    with transaction.atomic():
        with connection.cursor() as cur:
            cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        return capture_current_capital_payload()


class Command(BaseCommand):
    help = "Capture present-day capital or transfer an authenticated archival observation."

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group()
        group.add_argument("--export-json", action="store_true")
        group.add_argument("--import-stdin", action="store_true")
        parser.add_argument("--archive-at", help="ISO8601 timestamp of SQL-backup capture WITH offset; export only")
        parser.add_argument("--backup-sha256", help="sha256sum of the exact historical pg_dump file; export only")

    def handle(self, *args, **opts):
        if opts["import_stdin"]:
            if opts["archive_at"] or opts["backup_sha256"]:
                raise CommandError("Archive creation flags cannot be used during import.")
            try:
                document = json.loads(sys.stdin.read())
                stamp = datetime.fromisoformat(document["captured_at"])
                if stamp.tzinfo is None:
                    raise ValueError("Archive timestamp must include an offset")
                stamp = stamp.astimezone(timezone.get_current_timezone())
                if document["source"] != "archive":
                    raise ValueError("Only verified backup observations may be imported.")
                reference = str(document["backup_sha256"]).lower()
                if not re.fullmatch(r"[0-9a-f]{64}", reference):
                    raise ValueError("Invalid SHA-256 fingerprint.")
                if document["date"] != stamp.date().isoformat():
                    raise ValueError("Backup date does not match its timestamp.")
                if stamp.date() > timezone.localdate():
                    raise ValueError("Cannot import a future-dated snapshot.")
                payload = validate_capital_payload(document["data"])
                if str(payload.get("captured_at")) != document["captured_at"]:
                    raise ValueError("Payload timestamp differs from the backup capture.")
            except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
                raise CommandError(f"Rejected archival observation: {exc}") from exc
            with transaction.atomic():
                old = CapitalSnapshot.objects.select_for_update().filter(date=stamp.date()).first()
                if old:
                    if old.source != "archive" or old.source_reference != reference or old.data != payload:
                        raise CommandError("Different snapshot already exists for this date; no overwrite.")
                    self.stdout.write("ARCHIVE SNAPSHOT EXISTS: IDENTICAL; NO WRITE")
                    return
                CapitalSnapshot.objects.create(
                    date=stamp.date(), captured_at=stamp, source="archive",
                    source_reference=reference, data=payload,
                )
            self.stdout.write(self.style.SUCCESS(
                f"ARCHIVED SNAPSHOT IMPORTED {stamp.date()}: {payload['capital_total']}"
            ))
            return

        if bool(opts["archive_at"]) != bool(opts["backup_sha256"]):
            raise CommandError("--archive-at and --backup-sha256 must be supplied together.")
        if opts["archive_at"] and not opts["export_json"]:
            raise CommandError("Historical capture is export-only; never backdate the live DB.")
        payload = _read_consistent_current()
        if opts["export_json"]:
            if opts["archive_at"]:
                try:
                    stamp = datetime.fromisoformat(opts["archive_at"])
                    if stamp.tzinfo is None:
                        raise ValueError("Time-zone offset is mandatory")
                    fingerprint = str(opts["backup_sha256"]).lower()
                    if not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
                        raise ValueError("Full SHA-256 fingerprint is required")
                    stamp = stamp.astimezone(timezone.get_current_timezone())
                except ValueError as exc:
                    raise CommandError(str(exc)) from exc
                payload["captured_at"] = stamp.isoformat()
                data = {
                    "date": stamp.date().isoformat(), "captured_at": stamp.isoformat(),
                    "backup_sha256": fingerprint, "source": "archive", "data": payload,
                }
            else:
                stamp = datetime.fromisoformat(payload["captured_at"])
                data = {
                    "date": stamp.date().isoformat(), "captured_at": stamp.isoformat(),
                    "source": "live", "data": payload,
                }
            self.stdout.write(json.dumps(data, ensure_ascii=False, sort_keys=True))
            return

        # A live DB can capture ONLY its current actual business date. Running
        # this command tomorrow cannot create a fake yesterday balance.
        stamp = datetime.fromisoformat(payload["captured_at"])
        today = timezone.localdate()
        if stamp.date() != today:
            raise CommandError("Snapshot timestamp differs from current local date.")
        with transaction.atomic():
            existing = CapitalSnapshot.objects.select_for_update().filter(date=today).first()
            if existing and existing.source == "archive":
                raise CommandError("This date already has an archived snapshot; refusing overwrite.")
            if existing:
                existing.data = payload
                existing.captured_at = stamp
                existing.source_reference = ""
                existing.save(update_fields=["data", "captured_at", "source_reference", "updated_at"])
            else:
                CapitalSnapshot.objects.create(
                    date=today, captured_at=stamp, source="live", data=payload,
                )
        self.stdout.write(self.style.SUCCESS(
            f"TODAY CAPITAL SNAPSHOT {today} {stamp.isoformat()} CAPITAL={payload['capital_total']}"
        ))
