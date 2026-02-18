import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_alter_aircraftevent_category'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='aircraftnote',
            name='public',
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name='AircraftShareToken',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('token', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('label', models.CharField(blank=True, max_length=100)),
                ('privilege', models.CharField(
                    choices=[('status', 'Current Status'), ('maintenance', 'Maintenance Detail')],
                    default='status',
                    max_length=20,
                )),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('aircraft', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='share_tokens',
                    to='core.aircraft',
                )),
                ('created_by', models.ForeignKey(
                    editable=False,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
