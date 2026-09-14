from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Account",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=100, unique=True)),
                ("opening_balance", models.BigIntegerField(default=0)),
                ("active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["title"]},
        ),
        migrations.CreateModel(
            name="AppSetting",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=100, unique=True)),
                ("value", models.CharField(max_length=200)),
                ("label", models.CharField(max_length=160)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["key"]},
        ),
        migrations.CreateModel(
            name="Color",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=60, unique=True)),
                ("code", models.CharField(blank=True, max_length=20)),
                ("active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["name", "id"]},
        ),
        migrations.CreateModel(
            name="Product",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=60, unique=True)),
                ("title", models.CharField(blank=True, max_length=140)),
                ("active", models.BooleanField(default=True)),
                ("note", models.CharField(blank=True, max_length=250)),
            ],
            options={"ordering": ["code"]},
        ),
        migrations.CreateModel(
            name="SaleDay",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField(unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["-date"]},
        ),
        migrations.CreateModel(
            name="Size",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=30, unique=True)),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
                ("active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["sort_order", "id"]},
        ),
        migrations.CreateModel(
            name="StockLocation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.SlugField(max_length=30, unique=True)),
                ("title", models.CharField(max_length=80)),
                ("active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.CreateModel(
            name="AccountEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField(db_index=True)),
                ("delta", models.BigIntegerField()),
                ("title", models.CharField(max_length=180)),
                ("reference", models.CharField(blank=True, db_index=True, max_length=140)),
                ("note", models.CharField(blank=True, max_length=250)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="entries", to="dia_core.account")),
            ],
            options={"ordering": ["-date", "-id"]},
        ),
        migrations.CreateModel(
            name="Payment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField(db_index=True)),
                ("amount", models.PositiveBigIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ("title", models.CharField(max_length=160)),
                ("note", models.CharField(blank=True, max_length=250)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payments", to="dia_core.account")),
            ],
            options={"ordering": ["-date", "-id"]},
        ),
        migrations.CreateModel(
            name="Receipt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField(db_index=True)),
                ("amount", models.PositiveBigIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ("title", models.CharField(max_length=160)),
                ("note", models.CharField(blank=True, max_length=250)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="receipts", to="dia_core.account")),
            ],
            options={"ordering": ["-date", "-id"]},
        ),
        migrations.CreateModel(
            name="ProductVariant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("default_sale_price", models.PositiveBigIntegerField(default=0)),
                ("unit_cost", models.PositiveBigIntegerField(default=0)),
                ("active", models.BooleanField(default=True)),
                ("color", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="dia_core.color")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="variants", to="dia_core.product")),
                ("size", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="dia_core.size")),
            ],
            options={"ordering": ["product__code", "size__sort_order", "color__name"]},
        ),
        migrations.CreateModel(
            name="StockBalance",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("qty", models.IntegerField(default=0)),
                ("location", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stock_balances", to="dia_core.stocklocation")),
                ("variant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stock_balances", to="dia_core.productvariant")),
            ],
        ),
        migrations.CreateModel(
            name="InventoryAdjustment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField(db_index=True)),
                ("delta", models.IntegerField()),
                ("note", models.CharField(blank=True, max_length=250)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("location", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="dia_core.stocklocation")),
                ("variant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="adjustments", to="dia_core.productvariant")),
            ],
            options={"ordering": ["-date", "-id"]},
        ),
        migrations.CreateModel(
            name="InventoryMovement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField(db_index=True)),
                ("movement_type", models.CharField(choices=[("purchase", "خرید"), ("sale", "فروش"), ("return", "مرجوعی"), ("adjust", "اصلاح")], db_index=True, max_length=20)),
                ("delta", models.IntegerField()),
                ("reference", models.CharField(blank=True, db_index=True, max_length=140)),
                ("note", models.CharField(blank=True, max_length=250)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("location", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="dia_core.stocklocation")),
                ("variant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="dia_core.productvariant")),
            ],
            options={"ordering": ["-id"]},
        ),
        migrations.CreateModel(
            name="PurchaseLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField(db_index=True)),
                ("quantity", models.PositiveIntegerField(default=0)),
                ("inventory_applied_quantity", models.PositiveIntegerField(default=0)),
                ("unit_cost", models.PositiveBigIntegerField(default=0)),
                ("note", models.CharField(blank=True, max_length=250)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("variant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="purchase_lines", to="dia_core.productvariant")),
            ],
            options={"ordering": ["-date", "variant__product__code"]},
        ),
        migrations.CreateModel(
            name="ReturnRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField(db_index=True)),
                ("quantity", models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ("note", models.CharField(blank=True, max_length=250)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("variant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="returns", to="dia_core.productvariant")),
            ],
            options={"ordering": ["-date", "-id"]},
        ),
        migrations.CreateModel(
            name="SaleLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.PositiveIntegerField(default=0)),
                ("inventory_applied_quantity", models.PositiveIntegerField(default=0)),
                ("sale_price", models.PositiveBigIntegerField(default=0)),
                ("unit_cost_snapshot", models.PositiveBigIntegerField(default=0)),
                ("digikala_fee_unit", models.PositiveBigIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("day", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="dia_core.saleday")),
                ("variant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sale_lines", to="dia_core.productvariant")),
            ],
            options={"ordering": ["variant__product__code", "variant__size__sort_order", "variant__color__name"]},
        ),
        migrations.AddConstraint(
            model_name="productvariant",
            constraint=models.UniqueConstraint(fields=("product", "size", "color"), name="uniq_dia_product_variant"),
        ),
        migrations.AddConstraint(
            model_name="stockbalance",
            constraint=models.UniqueConstraint(fields=("variant", "location"), name="uniq_dia_variant_location"),
        ),
        migrations.AddConstraint(
            model_name="purchaseline",
            constraint=models.UniqueConstraint(fields=("date", "variant"), name="uniq_dia_purchase_date_variant"),
        ),
        migrations.AddConstraint(
            model_name="saleline",
            constraint=models.UniqueConstraint(fields=("day", "variant"), name="uniq_dia_day_variant"),
        ),
    ]
