from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("weather", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="weathersnapshot",
            name="details",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
