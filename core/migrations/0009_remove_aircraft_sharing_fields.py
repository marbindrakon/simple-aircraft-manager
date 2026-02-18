from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_migrate_share_tokens'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='aircraft',
            name='public_sharing_enabled',
        ),
        migrations.RemoveField(
            model_name='aircraft',
            name='share_token',
        ),
        migrations.RemoveField(
            model_name='aircraft',
            name='share_token_expires_at',
        ),
    ]
