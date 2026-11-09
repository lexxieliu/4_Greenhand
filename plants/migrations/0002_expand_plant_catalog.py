"""Expand Plant to the PRD 7.2 catalog schema and add PlantProblemSummary.

Existing rows keep their data: plant_name is renamed to common_name, every row gets a unique slug,
and free-text categories are mapped onto the new choices. Rows that existed before this migration have
no care data, so they are unpublished until a curator completes them in admin (or `seed_plants`
updates a row with the same slug); gardens that already use them keep working.
"""
import django.db.models.deletion
from django.db import migrations, models
from django.utils.text import slugify

CATEGORIES = {"herb", "leafy_green", "vegetable", "fruit", "root", "legume"}


def fill_slugs_and_categories(apps, schema_editor):
    Plant = apps.get_model("plants", "Plant")
    used = set()
    for plant in Plant.objects.order_by("plant_id"):
        base = slugify(plant.common_name) or f"plant-{plant.plant_id}"
        slug, n = base, 2
        while slug in used:
            slug, n = f"{base}-{n}", n + 1
        used.add(slug)
        category = (plant.category or "").strip().lower().replace(" ", "_").rstrip("s")
        plant.slug = slug
        plant.category = category if category in CATEGORIES else "vegetable"
        plant.save(update_fields=["slug", "category"])


def unpublish_rows_without_care_data(apps, schema_editor):
    apps.get_model("plants", "Plant").objects.filter(days_to_harvest_max__isnull=True).update(is_published=False)


class Migration(migrations.Migration):

    dependencies = [
        ("plants", "0001_initial"),
    ]

    operations = [
        migrations.RenameField("plant", "plant_name", "common_name"),
        migrations.AlterField("plant", "common_name", models.CharField(max_length=100, unique=True)),
        migrations.AlterField("plant", "scientific_name", models.CharField(blank=True, max_length=150)),
        migrations.AlterModelOptions("plant", {"ordering": ["common_name"]}),
        migrations.AddField("plant", "slug", models.SlugField(max_length=100, null=True)),
        migrations.RunPython(fill_slugs_and_categories, migrations.RunPython.noop),
        migrations.AlterField("plant", "slug", models.SlugField(max_length=100, unique=True)),
        migrations.AlterField("plant", "category", models.CharField(
            choices=[("herb", "Herb"), ("leafy_green", "Leafy green"), ("vegetable", "Vegetable"), ("fruit", "Fruit"),
                     ("root", "Root"), ("legume", "Legume")], default="vegetable", max_length=20)),
        migrations.AddField("plant", "difficulty", models.CharField(
            choices=[("easy", "Easy"), ("medium", "Medium"), ("hard", "Hard")], default="easy", max_length=10)),
        migrations.AddField("plant", "description", models.TextField(blank=True)),
        migrations.AddField("plant", "sunlight_requirement", models.CharField(
            choices=[("full_sun", "Full sun"), ("partial", "Partial sun"), ("shade", "Shade")], default="full_sun", max_length=10)),
        migrations.AddField("plant", "watering_interval_days", models.PositiveSmallIntegerField(default=3)),
        migrations.AddField("plant", "min_temp_c", models.DecimalField(blank=True, decimal_places=1, max_digits=4, null=True)),
        migrations.AddField("plant", "max_temp_c", models.DecimalField(blank=True, decimal_places=1, max_digits=4, null=True)),
        migrations.AddField("plant", "frost_tolerant", models.BooleanField(default=False)),
        migrations.AddField("plant", "frost_threshold_c", models.DecimalField(decimal_places=1, default=2.0, max_digits=4)),
        migrations.AddField("plant", "days_to_germination_min", models.PositiveSmallIntegerField(blank=True, null=True)),
        migrations.AddField("plant", "days_to_germination_max", models.PositiveSmallIntegerField(blank=True, null=True)),
        migrations.AddField("plant", "days_to_harvest_min", models.PositiveSmallIntegerField(blank=True, null=True)),
        migrations.AddField("plant", "days_to_harvest_max", models.PositiveSmallIntegerField(blank=True, null=True)),
        migrations.AddField("plant", "spacing_cm", models.PositiveSmallIntegerField(blank=True, null=True)),
        migrations.AddField("plant", "container_friendly", models.BooleanField(default=False)),
        migrations.AddField("plant", "indoor_friendly", models.BooleanField(default=False)),
        migrations.AddField("plant", "harvest_mode", models.CharField(
            choices=[("single", "Single harvest"), ("continuous", "Continuous harvest")], default="continuous", max_length=10)),
        migrations.AddField("plant", "hardiness_zones", models.JSONField(blank=True, default=list, help_text='Perennials only, e.g. ["4", "5", "6"]')),
        migrations.AddField("plant", "planting_months", models.JSONField(
            blank=True, default=dict, help_text='Outdoor planting months by zone, e.g. {"5b": [4, 5, 6]}; empty list = indoors any time')),
        migrations.AddField("plant", "care_guide", models.TextField(blank=True, help_text="One care tip per line")),
        migrations.AddField("plant", "external_source_id", models.CharField(blank=True, help_text="Perenual species id", max_length=40)),
        migrations.AddField("plant", "is_published", models.BooleanField(default=True)),
        migrations.RunPython(unpublish_rows_without_care_data, migrations.RunPython.noop),
        migrations.CreateModel(
            name="PlantProblemSummary",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("problem_name", models.CharField(max_length=120)),
                ("symptoms", models.TextField()),
                ("solution", models.TextField()),
                ("source_count", models.PositiveIntegerField(default=0)),
                ("generated_at", models.DateTimeField(auto_now_add=True)),
                ("plant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="problem_summaries", to="plants.plant")),
            ],
            options={"ordering": ["-source_count", "problem_name"], "verbose_name_plural": "plant problem summaries"},
        ),
    ]
