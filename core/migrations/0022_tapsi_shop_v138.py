from decimal import Decimal

from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


class Migration(migrations.Migration):
    dependencies = [("core", "0021_material_color_use_v123")]

    operations = [
        migrations.CreateModel(
            name="TapsiOrder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("shipping_fee", models.PositiveBigIntegerField(default=140000)),
                ("commission_percent", models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("15.00"))),
                ("discount_cost", models.PositiveBigIntegerField(default=0)),
                ("note", models.CharField(blank=True, default="", max_length=300)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("day", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tapsi_orders", to="core.saleday")),
            ],
            options={"ordering": ["-id"]},
        ),
        migrations.CreateModel(
            name="TapsiPriceRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("effective_from", models.DateField(db_index=True)),
                ("price", models.PositiveBigIntegerField()),
                ("product_size", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="tapsi_price_rules", to="core.productsize")),
            ],
            options={"ordering": ["-effective_from", "-id"]},
        ),
        migrations.CreateModel(
            name="TapsiOrderItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ("unit_price", models.PositiveBigIntegerField()),
                ("unit_cost", models.PositiveBigIntegerField(default=0)),
                ("pack_qty", models.PositiveIntegerField(default=1)),
                ("code_snapshot", models.CharField(blank=True, default="", max_length=50)),
                ("title_snapshot", models.CharField(blank=True, default="", max_length=160)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="core.tapsiorder")),
                ("product_size", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="core.productsize")),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.CreateModel(
            name="TapsiStockAllocation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="stock_allocations", to="core.tapsiorderitem")),
                ("color", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="core.color")),
                ("location", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="core.stocklocation")),
            ],
        ),
        migrations.AddConstraint(
            model_name="tapsipricerule",
            constraint=models.UniqueConstraint(fields=("product_size", "effective_from"), name="uniq_tapsi_price_date"),
        ),
        migrations.AddConstraint(
            model_name="tapsiorderitem",
            constraint=models.UniqueConstraint(fields=("order", "product_size"), name="uniq_tapsi_order_product_size"),
        ),
        migrations.AddConstraint(
            model_name="tapsistockallocation",
            constraint=models.UniqueConstraint(fields=("item", "color", "location"), name="uniq_tapsi_item_color_location"),
        ),
    ]
