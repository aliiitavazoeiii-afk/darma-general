from django.db import migrations


CATEGORIES = [
    ("غذا", "food", "coral", 10),
    ("VPN", "vpn", "violet", 20),
    ("کار", "work", "amber", 30),
    ("ماشین", "car", "blue", 40),
    ("تفریح", "fun", "cyan", 50),
    ("روزمره", "daily", "green", 60),
]


def seed_categories(apps, schema_editor):
    Category = apps.get_model("expense_tracker", "ExpenseCategory")
    for name, slug, accent, sort_order in CATEGORIES:
        Category.objects.get_or_create(
            slug=slug,
            defaults={
                "name": name,
                "accent": accent,
                "sort_order": sort_order,
                "active": True,
            },
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("expense_tracker", "0001_initial")]

    operations = [
        migrations.RunPython(seed_categories, noop_reverse),
    ]
