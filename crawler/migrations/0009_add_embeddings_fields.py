from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crawler", "0008_add_screenshot_path"),
    ]

    operations = [
        migrations.AddField(
            model_name="crawledpage",
            name="section_embeddings",
            field=models.JSONField(
                default=list,
                help_text="Per-section embeddings (model: text-embedding-3-small)",
            ),
        ),
        migrations.AddField(
            model_name="crawledpage",
            name="page_embedding",
            field=models.JSONField(
                default=list,
                help_text="Full-page embedding (model: text-embedding-3-small)",
            ),
        ),
    ]


