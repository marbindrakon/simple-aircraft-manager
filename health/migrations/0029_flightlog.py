import django.db.models.deletion
import health.models
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0012_aircraft_tach_hobbs_fields'),
        ('health', '0028_excluded_from_averages'),
    ]

    operations = [
        migrations.CreateModel(
            name='FlightLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('date', models.DateField()),
                ('tach_time', models.DecimalField(decimal_places=1, max_digits=6)),
                ('tach_out', models.DecimalField(blank=True, decimal_places=1, max_digits=8, null=True)),
                ('tach_in', models.DecimalField(blank=True, decimal_places=1, max_digits=8, null=True)),
                ('hobbs_time', models.DecimalField(blank=True, decimal_places=1, max_digits=6, null=True)),
                ('hobbs_out', models.DecimalField(blank=True, decimal_places=1, max_digits=8, null=True)),
                ('hobbs_in', models.DecimalField(blank=True, decimal_places=1, max_digits=8, null=True)),
                ('departure_location', models.CharField(blank=True, max_length=10)),
                ('destination_location', models.CharField(blank=True, max_length=10)),
                ('route', models.TextField(blank=True)),
                ('oil_added', models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ('oil_added_type', models.CharField(blank=True, max_length=100)),
                ('fuel_added', models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ('fuel_added_type', models.CharField(blank=True, max_length=100)),
                ('track_log', models.FileField(blank=True, null=True, upload_to=health.models.random_track_log_filename)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('aircraft', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='flight_logs', to='core.aircraft')),
            ],
            options={
                'ordering': ['-date', '-created_at'],
            },
        ),
    ]
