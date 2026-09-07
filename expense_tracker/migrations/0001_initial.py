from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ExpenseCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80, unique=True)),
                ("slug", models.SlugField(allow_unicode=True, max_length=100, unique=True)),
                ("accent", models.CharField(default="green", max_length=24)),
                ("active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "دسته هزینه",
                "verbose_name_plural": "دسته‌های هزینه",
                "ordering": ("sort_order", "id"),
            },
        ),
        migrations.CreateModel(
            name="ReceivablePerson",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True)),
                ("note", models.CharField(blank=True, max_length=250)),
                ("active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "شخص بدهکار",
                "verbose_name_plural": "اشخاص بدهکار",
                "ordering": ("name", "id"),
            },
        ),
        migrations.CreateModel(
            name="DailyExpense",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField(db_index=True)),
                ("amount", models.BigIntegerField()),
                ("title", models.CharField(blank=True, max_length=160)),
                ("note", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("category", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="expenses", to="expense_tracker.expensecategory")),
            ],
            options={
                "verbose_name": "هزینه",
                "verbose_name_plural": "هزینه‌ها",
                "ordering": ("-date", "-created_at", "-id"),
            },
        ),
        migrations.CreateModel(
            name="ReceivableEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField(db_index=True)),
                ("kind", models.CharField(choices=[("claim", "طلب"), ("payment", "تسویه")], max_length=12)),
                ("amount", models.BigIntegerField()),
                ("note", models.CharField(blank=True, max_length=250)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("person", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="entries", to="expense_tracker.receivableperson")),
            ],
            options={
                "verbose_name": "گردش طلب",
                "verbose_name_plural": "گردش طلب‌ها",
                "ordering": ("-date", "-created_at", "-id"),
            },
        ),
        migrations.AddIndex(
            model_name="dailyexpense",
            index=models.Index(fields=["date", "category"], name="exp_date_category_idx"),
        ),
        migrations.AddConstraint(
            model_name="dailyexpense",
            constraint=models.CheckConstraint(condition=models.Q(("amount__gt", 0)), name="expense_amount_positive"),
        ),
        migrations.AddIndex(
            model_name="receivableentry",
            index=models.Index(fields=["person", "kind"], name="recv_person_kind_idx"),
        ),
        migrations.AddConstraint(
            model_name="receivableentry",
            constraint=models.CheckConstraint(condition=models.Q(("amount__gt", 0)), name="receivable_amount_positive"),
        ),
    ]
