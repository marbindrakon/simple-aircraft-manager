from django.db import migrations


def migrate_share_tokens(apps, schema_editor):
    Aircraft = apps.get_model('core', 'Aircraft')
    AircraftShareToken = apps.get_model('core', 'AircraftShareToken')

    for aircraft in Aircraft.objects.filter(
        public_sharing_enabled=True,
        share_token__isnull=False,
    ):
        AircraftShareToken.objects.create(
            aircraft=aircraft,
            token=aircraft.share_token,
            label='Migrated link',
            privilege='maintenance',
            expires_at=aircraft.share_token_expires_at,
        )


def reverse_migrate(apps, schema_editor):
    # No-op: we can't safely restore the old fields from tokens
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_aircraftsharetoken_aircraftnote_public'),
    ]

    operations = [
        migrations.RunPython(migrate_share_tokens, reverse_migrate),
    ]
