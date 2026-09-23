from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0017_digikalasettlement_source")]

    operations = [
        migrations.CreateModel(
            name="CapitalSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField(db_index=True, unique=True)),
                ("captured_at", models.DateTimeField()),
                ("source", models.CharField(max_length=16, default="live", choices=[("live", "Live"), ("archive", "Verified backup")])),
                ("source_reference", models.CharField(blank=True, max_length=255)),
                ("data", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["-date"]},
        )
    ]
