from django.db import migrations, models


def migrate_shared_to_visibility(apps, schema_editor):
    """Convert existing shared bool/nullable-bool to visibility CharField."""
    DocumentCollection = apps.get_model('health', 'DocumentCollection')
    Document = apps.get_model('health', 'Document')

    for col in DocumentCollection.objects.all():
        col.visibility = 'status' if col.shared else 'private'
        col.save(update_fields=['visibility'])

    for doc in Document.objects.all():
        if doc.shared is True:
            doc.visibility = 'status'
        elif doc.shared is False:
            doc.visibility = 'private'
        else:
            doc.visibility = None
        doc.save(update_fields=['visibility'])


class Migration(migrations.Migration):

    dependencies = [
        ('health', '0019_alter_documentimage_options_documentimage_order'),
    ]

    operations = [
        # Add new visibility fields (nullable during transition)
        migrations.AddField(
            model_name='documentcollection',
            name='visibility',
            field=models.CharField(
                choices=[
                    ('private', 'Private'),
                    ('status', 'All share links'),
                    ('maintenance', 'Maintenance only'),
                ],
                default='private',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='document',
            name='visibility',
            field=models.CharField(
                blank=True,
                choices=[
                    ('private', 'Private'),
                    ('status', 'All share links'),
                    ('maintenance', 'Maintenance only'),
                ],
                default=None,
                max_length=20,
                null=True,
            ),
        ),
        # Data migration: populate visibility from shared
        migrations.RunPython(migrate_shared_to_visibility, migrations.RunPython.noop),
        # Remove old shared fields
        migrations.RemoveField(
            model_name='documentcollection',
            name='shared',
        ),
        migrations.RemoveField(
            model_name='document',
            name='shared',
        ),
    ]
