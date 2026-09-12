from django.db import migrations, models


def mark_existing_payments_applied(apps, schema_editor):
    ReceivableEntry = apps.get_model("expense_tracker", "ReceivableEntry")
    ReceivableEntry.objects.filter(kind="payment").update(mellat_applied=True)


def unmark_existing_payments(apps, schema_editor):
    ReceivableEntry = apps.get_model("expense_tracker", "ReceivableEntry")
    ReceivableEntry.objects.filter(kind="payment").update(mellat_applied=False)


class Migration(migrations.Migration):

    dependencies = [
        ("expense_tracker", "0002_seed_categories"),
    ]

    operations = [
        migrations.AddField(
            model_name="receivableentry",
            name="mellat_applied",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(mark_existing_payments_applied, unmark_existing_payments),
    ]
