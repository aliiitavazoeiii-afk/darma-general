from django.db import migrations, models


def attach_orphan_colors_to_darma(apps, schema_editor):
    Brand = apps.get_model("core", "Brand")
    Color = apps.get_model("core", "Color")
    Size = apps.get_model("core", "Size")
    StockLocation = apps.get_model("core", "StockLocation")
    StockBalance = apps.get_model("core", "StockBalance")
    ProductComposition = apps.get_model("core", "ProductComposition")
    InventoryModelCost = apps.get_model("core", "InventoryModelCost")

    darma = Brand.objects.filter(name="دارما").first()
    home = StockLocation.objects.filter(key="home").first()
    khorshid = StockLocation.objects.filter(key="khorshid").first()
    if not darma or not home:
        return

    connected = set(StockBalance.objects.values_list("color_id", flat=True))
    connected.update(ProductComposition.objects.values_list("color_id", flat=True))
    orphan_colors = Color.objects.filter(active=True).exclude(id__in=connected)
    sizes = list(Size.objects.all().order_by("sort_order", "id"))

    for color in orphan_colors:
        for size in sizes:
            StockBalance.objects.get_or_create(
                brand=darma, size=size, color=color, location=home,
                defaults={"qty": 0},
            )
            if khorshid:
                StockBalance.objects.get_or_create(
                    brand=darma, size=size, color=color, location=khorshid,
                    defaults={"qty": 0},
                )
            InventoryModelCost.objects.get_or_create(
                brand=darma, color=color, size=size,
                defaults={"unit_cost": 0},
            )


class Migration(migrations.Migration):
    dependencies = [("core", "0008_payments")]

    operations = [
        migrations.AlterField(
            model_name="rawmaterialstock",
            name="location",
            field=models.CharField(
                choices=[("warehouse", "انبار"), ("tailor", "خیاط"), ("depot", "دپو")],
                db_index=True,
                max_length=20,
            ),
        ),
        migrations.RunPython(attach_orphan_colors_to_darma, migrations.RunPython.noop),
    ]
