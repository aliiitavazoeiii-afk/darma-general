"""V144 fees: historical orders retain zero insurance and infrastructure rates."""
from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0023_tapsi_commission_vat_v143")]

    operations = [
        migrations.AddField(
            model_name="tapsiorder",
            name="insurance_percent",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=5),
        ),
        migrations.AddField(
            model_name="tapsiorder",
            name="infrastructure_percent",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=5),
        ),
    ]
