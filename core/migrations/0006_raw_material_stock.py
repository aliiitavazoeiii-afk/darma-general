from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0005_inventory_model_cost")]

    operations = [
        migrations.CreateModel(
            name="RawMaterialStock",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("fabric", "پارچه"), ("elastic", "کش")], db_index=True, max_length=20)),
                ("location", models.CharField(choices=[("warehouse", "انبار"), ("tailor", "خیاط")], db_index=True, max_length=20)),
                ("title", models.CharField(max_length=120)),
                ("quantity", models.DecimalField(decimal_places=3, default=Decimal("0"), max_digits=14)),
                ("unit_price", models.PositiveBigIntegerField(default=0)),
                ("unit", models.CharField(default="کیلو", max_length=20)),
                ("note", models.CharField(blank=True, max_length=250)),
                ("active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["kind", "location", "id"]},
        ),
    ]
