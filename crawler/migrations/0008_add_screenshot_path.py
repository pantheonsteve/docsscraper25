# Generated manually for screenshot feature

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crawler', '0007_rename_crawler_cra_client__idx_crawler_cra_client__31735a_idx'),
    ]

    operations = [
        migrations.AddField(
            model_name='crawledpage',
            name='screenshot_path',
            field=models.CharField(blank=True, help_text='Path to page screenshot', max_length=500, null=True),
        ),
    ]

