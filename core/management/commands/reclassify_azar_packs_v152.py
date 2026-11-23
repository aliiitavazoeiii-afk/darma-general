"""V152 exact one-off inventory reclassification of booked Darma pack sales.

Default: read-only complete preview. --apply: one atomic, validated repair
of the already-applied SaleAllocation rows and Darma HOME balances. No
SaleLine, accounting, sale snapshot, product recipe, stock transfer, invoice,
or production data is rewritten.

Running --apply repeatedly is idempotent. Subsequent reimports also keep
the date-effective colors through effective_sale_compositions() used by
sync_sale_inventory().
"""
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Sum

from core.azar_pack_colors_v152 import (
    BRAND_NAME, RED, RULES, START_DATE, color_for_name,
    correction_rule, effective_sale_compositions,
)
from core.models import (
    InventoryMovement, ProductComposition, SaleAllocation,
    SaleLine, SaleShortage, StockBalance, StockLocation,
)


@dataclass
class Plan:
    line_id: int
    when: date
    code: str
    size: str
    packs: int
    stock_brand_id: int
    size_id: int
    source_color_id: int
    red_color_id: int
    source_name: str
    old_source: int
    new_source: int
    old_red: int
    new_red: int
    delta: int
    status: str


def eligible_lines(lock=False):
    q = (
        SaleLine.objects.filter(
            day__date__gte=START_DATE,
            product_size__product__brand__name=BRAND_NAME,
            product_size__product__code__in=tuple(RULES),
            quantity__gt=0,
        )
        .select_related("day", "product_size__product__brand", "product_size__size")
        .order_by("day__date", "id")
    )
    return q.select_for_update() if lock else q


def make_plan(line, home, *, lock=False):
    rule = correction_rule(line)
    if not rule:
        raise ValueError(f"فروش {line.pk} خارج از بازه یا کد مجاز است.")
    pack_qty, source_name, replacement = rule
    # Checks original recipe, source color and target color BEFORE any write.
    effective_sale_compositions(line)
    source = color_for_name(source_name)
    red = color_for_name(RED)
    existing = {
        c.color_id: int(c.qty)
        for c in ProductComposition.objects.filter(product=line.product_size.product)
    }
    source_each = existing.get(source.pk, 0)
    red_each = existing.get(red.pk, 0)
    qty = int(line.quantity)
    if int(line.inventory_applied_quantity or 0) != qty:
        raise ValueError(
            f"فروش {line.pk} ({line.product_size.product.code}/{line.product_size.size.name}) "
            f"هنوز کامل روی موجودی اعمال نشده ({line.inventory_applied_quantity}/{qty})."
        )

    allocs = SaleAllocation.objects.filter(sale_line=line).order_by("id")
    if lock:
        allocs = allocs.select_for_update()
    allocs = list(allocs)
    if sum(int(a.qty) for a in allocs) != qty * pack_qty:
        raise ValueError(
            f"فروش {line.pk}: تعداد تخصیص موجودی با {qty} پک {pack_qty}تایی برابر نیست."
        )
    if any(a.location_id != home.pk for a in allocs):
        raise ValueError(f"فروش {line.pk}: تخصیص غیر از انبار خانه دارد؛ بررسی دستی لازم است.")
    if any(a.is_replacement and a.color_id in (source.pk, red.pk) for a in allocs):
        raise ValueError(f"فروش {line.pk}: جایگزینی قبلی روی رنگ مبدأ/قرمز دارد؛ بررسی دستی لازم است.")

    shortages = SaleShortage.objects.filter(sale_line=line)
    if shortages.filter(source_color_id__in=[source.pk, red.pk]).exists() or shortages.filter(
        target_color_id__in=[source.pk, red.pk]
    ).exists():
        raise ValueError(
            f"فروش {line.pk}: کسری/جایگزینی ثبت‌شده برای رنگ مبدأ یا قرمز دارد؛ "
            "برای جلوگیری از دست‌کاری تاریخچه کسری، اصلاح خودکار متوقف شد."
        )
    summed = defaultdict(int)
    for alloc in allocs:
        summed[alloc.color_id] += int(alloc.qty)
    current_source = summed[source.pk]
    current_red = summed[red.pk]
    old_source = source_each * qty
    new_source = (source_each - replacement) * qty
    old_red = red_each * qty
    new_red = (red_each + replacement) * qty

    if current_source == new_source and current_red == new_red:
        status = "already"
    elif current_source == old_source and current_red == old_red:
        status = "pending"
    else:
        raise ValueError(
            f"فروش {line.pk} ({line.day.date}/{line.product_size.size.name}): "
            f"تخصیص فعلی {source_name}={current_source}، قرمز={current_red} "
            f"با قبل یا بعد اصلاح سازگار نیست؛ تغییر خودکار خطرناک است."
        )

    return Plan(
        line_id=line.id,
        when=line.day.date,
        code=line.product_size.product.code,
        size=line.product_size.size.name,
        packs=qty,
        stock_brand_id=line.product_size.product.brand_id,
        size_id=line.product_size.size_id,
        source_color_id=source.pk,
        red_color_id=red.pk,
        source_name=source_name,
        old_source=old_source,
        new_source=new_source,
        old_red=old_red,
        new_red=new_red,
        delta=qty * replacement,
        status=status,
    )


def apply_plan(plan, home):
    if plan.status != "pending":
        return
    balances = {}
    for color_id in sorted((plan.source_color_id, plan.red_color_id)):
        row, _ = StockBalance.objects.get_or_create(
            brand_id=plan.stock_brand_id, size_id=plan.size_id,
            color_id=color_id, location=home,
            defaults={"qty": 0},
        )
        balances[color_id] = StockBalance.objects.select_for_update().get(pk=row.pk)

    balance = balances[plan.source_color_id]
    balance.qty += plan.delta
    balance.save(update_fields=["qty"])
    balance = balances[plan.red_color_id]
    balance.qty -= plan.delta  # Negative HOME inventory is permitted.
    balance.save(update_fields=["qty"])

    amount_left = plan.delta
    allocations = SaleAllocation.objects.select_for_update().filter(
        sale_line_id=plan.line_id,
        color_id=plan.source_color_id,
        location=home, is_replacement=False,
    ).order_by("id")
    for alloc in allocations:
        taken = min(int(alloc.qty), amount_left)
        if not taken:
            break
        if int(alloc.qty) == taken:
            alloc.delete()
        else:
            alloc.qty -= taken
            alloc.save(update_fields=["qty"])
        amount_left -= taken
    if amount_left:
        raise RuntimeError(f"فروش {plan.line_id}: تخصیص کافی برای بازطبقه‌بندی نبود.")

    SaleAllocation.objects.create(
        sale_line_id=plan.line_id,
        color_id=plan.red_color_id,
        location=home,
        qty=plan.delta,
        is_replacement=False,
    )
    reference = f"v152:azar-color:sale:{plan.line_id}"
    for color_id, delta in (
        (plan.source_color_id, plan.delta),
        (plan.red_color_id, -plan.delta),
    ):
        InventoryMovement.objects.create(
            movement_type=InventoryMovement.ADJUST,
            brand_id=plan.stock_brand_id,
            size_id=plan.size_id,
            color_id=color_id,
            location=home,
            delta=delta,
            reference=reference,
        )

    # Reconciling both signed stock movements and per-sale inventory.
    now = defaultdict(int)
    for entry in SaleAllocation.objects.filter(sale_line_id=plan.line_id):
        now[entry.color_id] += int(entry.qty)
    if now[plan.source_color_id] != plan.new_source or now[plan.red_color_id] != plan.new_red:
        raise RuntimeError(f"فروش {plan.line_id}: موجودی بعد از تغییر تطبیق ندارد.")


class Command(BaseCommand):
    help = "V152: reclassify booked Darma 06 cream->red and p12 gray(2)->red(2), from 1405/09/01."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply", action="store_true",
            help="Apply all verified historical reclassifications atomically (default is read-only)."
        )

    def handle(self, *args, **options):
        apply = bool(options["apply"])
        with transaction.atomic():
            home = StockLocation.objects.filter(key=StockLocation.HOME).first()
            if not home:
                raise CommandError("انبار خانه وجود ندارد؛ هیچ تغییری اعمال نشد.")
            lines = list(eligible_lines(lock=apply))
            plans = []
            errors = []
            for line in lines:
                try:
                    plans.append(make_plan(line, home, lock=apply))
                except ValueError as e:
                    errors.append(f"#{line.pk} / {line.day.date} / {line.product_size.product.code}: {e}")
            if errors:
                for error in errors:
                    self.stderr.write("STOP: " + error)
                raise CommandError(
                    f"{len(errors)} فروش نامعتبر؛ هیچ تغییری روی موجودی اعمال نشد."
                )
            totals = defaultdict(lambda: {"packs": 0, "pieces": 0, "pending": 0, "done": 0})
            for plan in plans:
                row = totals[plan.code]
                row["packs"] += plan.packs
                row["pieces"] += plan.delta
                row["pending" if plan.status == "pending" else "done"] += 1
                self.stdout.write(
                    f"{plan.when} | {plan.code} / {plan.size} | sale_id={plan.line_id} "
                    f"| packs={plan.packs} | {plan.source_name} -> قرمز: {plan.delta} "
                    f"| {plan.status}"
                )
            for code in RULES:
                row = totals[code]
                self.stdout.write(
                    f"V152_SUMMARY_{code}: packs={row['packs']} color_pieces={row['pieces']} "
                    f"pending_lines={row['pending']} already_corrected={row['done']}"
                )
            if not apply:
                self.stdout.write("V152_DRY_RUN=OK; no sales, stock or accounting records changed.")
                return
            for plan in plans:
                apply_plan(plan, home)
            changed = sum(p.status == "pending" for p in plans)
            self.stdout.write(
                self.style.SUCCESS(
                    f"V152_APPLIED=OK corrected_lines={changed}, "
                    f"unchanged_lines={len(plans)-changed}; "
                    "sale prices, quantities, costs and Digikala receivables untouched."
                )
            )
