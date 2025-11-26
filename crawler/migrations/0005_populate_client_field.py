# Data migration to populate client field from job

from django.db import migrations


def populate_client_field(apps, schema_editor):
    """Populate the client field from the job's client."""
    CrawledPage = apps.get_model('crawler', 'CrawledPage')
    
    # Update all pages with their client from job
    pages_updated = 0
    for page in CrawledPage.objects.select_related('job__client').iterator(chunk_size=1000):
        page.client = page.job.client
        page.save(update_fields=['client'])
        pages_updated += 1
        
        if pages_updated % 1000 == 0:
            print(f"Populated {pages_updated} pages...")
    
    print(f"Finished: Populated client field for {pages_updated} pages")


def reverse_populate_client_field(apps, schema_editor):
    """Reverse migration - set client to null."""
    CrawledPage = apps.get_model('crawler', 'CrawledPage')
    CrawledPage.objects.update(client=None)


class Migration(migrations.Migration):

    dependencies = [
        ('crawler', '0004_add_client_to_crawledpage'),
    ]

    operations = [
        migrations.RunPython(
            populate_client_field,
            reverse_populate_client_field
        ),
    ]
