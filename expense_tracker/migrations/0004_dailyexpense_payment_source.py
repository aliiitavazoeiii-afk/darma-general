from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("expense_tracker", "0003_receivable_mellat_applied"),
    ]

    operations = [
        migrations.AddField(
            model_name="dailyexpense",
            name="payment_source",
            field=models.CharField(
                choices=[("melat", "ملت"), ("mofid", "مفید")],
                db_index=True,
                default="melat",
                max_length=16,
            ),
        ),
    ]
