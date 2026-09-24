from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0017_digikalasettlement_source"),
    ]

    operations = [
        migrations.CreateModel(
            name="PriceMonitorEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("planned", "برنامه‌ریزی‌شده"), ("applied", "اعمال‌شده")], db_index=True, max_length=12)),
                ("old_price", models.PositiveBigIntegerField(default=0)),
                ("new_price", models.PositiveBigIntegerField()),
                ("planned_for", models.DateField(blank=True, null=True)),
                ("effective_date", models.DateField(blank=True, db_index=True, null=True)),
                ("effective_time", models.TimeField(blank=True, null=True)),
                ("reason", models.CharField(blank=True, max_length=240)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("corrects", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="corrections", to="core.pricemonitorevent")),
                ("product_size", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="price_monitor_events", to="core.productsize")),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.CreateModel(
            name="PriceMonitorPin",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("product_size", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="price_monitor_pin", to="core.productsize")),
            ],
        ),
        migrations.CreateModel(
            name="PriceMonitorPaymentSplit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("cash_packs", models.PositiveIntegerField(default=0)),
                ("credit_packs", models.PositiveIntegerField(default=0)),
                ("credit_extra_fee", models.PositiveBigIntegerField(blank=True, null=True)),
                ("fee_basis", models.CharField(choices=[("unknown", "نامشخص"), ("included_in_report", "در کارمزد گزارش اصلی منظور شده"), ("additional_documented", "کارمزد اضافه با سند مستقل؛ صرفاً سناریوی تحلیلی")], default="unknown", max_length=32)),
                ("evidence_reference", models.CharField(blank=True, max_length=120)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("sale_line", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="price_monitor_split", to="core.saleline")),
            ],
        ),
    ]
