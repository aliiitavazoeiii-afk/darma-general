"""V143: snapshot VAT rate on Tapsi commission; previous orders remain 0% VAT."""
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0022_tapsi_shop_v138"),
    ]

    operations = [
        migrations.AddField(
            model_name="tapsiorder",
            name="vat_percent",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=5),
        ),
    ]
