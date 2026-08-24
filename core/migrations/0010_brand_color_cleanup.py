from django.db import migrations


TAKVIN = [
    "طوسی راه راه", "زرد", "بنفش", "طوسی", "سرمه ای", "سفید", "چرک روشن",
    "مشکی", "راه راه بنفش", "راه راه سفید مشکی", "راه راه زرد", "متفرقه",
    "راه راه طوسی", "راه راه سفید", "راه راه مشکی",
]
DARMA = [
    "مشکی", "سفید", "سرمه ای", "صورتی", "کرم", "قرمز", "زرد", "طوسی",
    "راه راه", "راه راه طوسی", "برعکس مشکی", "برعکس سفید", "برعکس سرمه ای",
]


def norm(value):
    return (value or "").replace("ي", "ی").replace("ك", "ک").replace("‌", "").replace(" ", "").strip().lower()


def separate_colors(apps, schema_editor):
    Brand = apps.get_model("core", "Brand")
    Color = apps.get_model("core", "Color")
    Size = apps.get_model("core", "Size")
    StockLocation = apps.get_model("core", "StockLocation")
    StockBalance = apps.get_model("core", "StockBalance")
    StockThreshold = apps.get_model("core", "StockThreshold")
    InventoryModelCost = apps.get_model("core", "InventoryModelCost")

    darma = Brand.objects.filter(name="دارما").first()
    takvin = Brand.objects.filter(name="تکوین").first()
    home = StockLocation.objects.filter(key="home").first()
    khorshid = StockLocation.objects.filter(key="khorshid").first()
    if not darma or not takvin or not home:
        return

    takvin_norm = {norm(x) for x in TAKVIN}
    darma_norm = {norm(x) for x in DARMA}
    shared = takvin_norm & darma_norm

    colors = list(Color.objects.filter(active=True).order_by("id"))
    by_norm = {}
    for color in colors:
        by_norm.setdefault(norm(color.name), color)

    # Takvin is intentionally limited to the exact workbook catalog.
    allowed_takvin_ids = {color.id for color in colors if norm(color.name) in takvin_norm}
    StockBalance.objects.filter(brand=takvin).exclude(color_id__in=allowed_takvin_ids).delete()
    InventoryModelCost.objects.filter(brand=takvin).exclude(color_id__in=allowed_takvin_ids).delete()
    StockThreshold.objects.filter(brand=takvin).exclude(color_id__in=allowed_takvin_ids).delete()

    takvin_sizes = list(Size.objects.filter(name__in=["M", "L", "XL", "XXL"]))
    for color in colors:
        if norm(color.name) not in takvin_norm:
            continue
        for size in takvin_sizes:
            StockBalance.objects.get_or_create(brand=takvin, color=color, size=size, location=home, defaults={"qty": 0})
    StockBalance.objects.filter(brand=takvin, location__key="khorshid").delete()

    # Darma keeps its canonical colors plus every user-added color that is not
    # an exclusive Takvin color. Shared colors remain available to both brands.
    darma_allowed = []
    for color in colors:
        n = norm(color.name)
        if n in takvin_norm and n not in shared and n not in darma_norm:
            continue
        darma_allowed.append(color)
    allowed_darma_ids = {color.id for color in darma_allowed}
    StockBalance.objects.filter(brand=darma).exclude(color_id__in=allowed_darma_ids).delete()
    InventoryModelCost.objects.filter(brand=darma).exclude(color_id__in=allowed_darma_ids).delete()
    StockThreshold.objects.filter(brand=darma).exclude(color_id__in=allowed_darma_ids).delete()

    darma_sizes = list(Size.objects.all().order_by("sort_order", "id"))
    for color in darma_allowed:
        for size in darma_sizes:
            StockBalance.objects.get_or_create(brand=darma, color=color, size=size, location=home, defaults={"qty": 0})
            if khorshid:
                StockBalance.objects.get_or_create(brand=darma, color=color, size=size, location=khorshid, defaults={"qty": 0})


class Migration(migrations.Migration):
    dependencies = [("core", "0009_material_depot_and_default_darma_colors")]
    operations = [migrations.RunPython(separate_colors, migrations.RunPython.noop)]
