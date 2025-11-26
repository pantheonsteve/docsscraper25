# Migration to make client field non-nullable and add unique constraint

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('crawler', '0005_populate_client_field'),
    ]

    operations = [
        # Make client field non-nullable
        migrations.AlterField(
            model_name='crawledpage',
            name='client',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='pages',
                to='core.client'
            ),
        ),
        
        # Add new unique constraint for client + url
        migrations.AlterUniqueTogether(
            name='crawledpage',
            unique_together={('client', 'url')},
        ),
    ]
