from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_invitationcode_invitationcodeaircraftrole_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='aircraft',
            old_name='flight_time',
            new_name='tach_time',
        ),
        migrations.AddField(
            model_name='aircraft',
            name='tach_time_offset',
            field=models.DecimalField(decimal_places=1, default=0.0, max_digits=8),
        ),
        migrations.AddField(
            model_name='aircraft',
            name='hobbs_time',
            field=models.DecimalField(decimal_places=1, default=0.0, max_digits=8),
        ),
        migrations.AddField(
            model_name='aircraft',
            name='hobbs_time_offset',
            field=models.DecimalField(decimal_places=1, default=0.0, max_digits=8),
        ),
    ]
