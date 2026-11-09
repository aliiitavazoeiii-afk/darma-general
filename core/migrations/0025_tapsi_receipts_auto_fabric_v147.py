"""V147: additive Tapsi receipts option and auditable sheet-owned fabric transfers."""
from decimal import Decimal
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("core", "0024_tapsi_insurance_infrastructure_v144")]
    operations = [
        migrations.AlterField(
            model_name="digikalasettlement",
            name="source",
            field=models.CharField(
                choices=[
                    ("digikala", "دیجی‌کالا"),
                    ("dia_gallery", "Dia Gallery"),
                    ("tapsi", "تپسی‌شاپ"),
                ],
                db_index=True, default="digikala", max_length=30,
            ),
        ),
        migrations.CreateModel(
            name="MaterialReportFabricTransfer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("material_key", models.CharField(max_length=40)),
                ("quantity", models.DecimalField(decimal_places=3, default=Decimal("0.000"), max_digits=14)),
                ("block", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="auto_fabric_transfers", to="core.materialreportblock")),
                ("source", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="production_fabric_out", to="core.rawmaterialstock")),
                ("tailor_stock", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="production_fabric_in", to="core.rawmaterialstock")),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.AddConstraint(
            model_name="materialreportfabrictransfer",
            constraint=models.UniqueConstraint(
                fields=("block", "material_key", "source"),
                name="uniq_production_auto_fabric_source",
            ),
        ),
    ]
