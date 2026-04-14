import django.db.models.deletion
import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        # Depend on the core app's initial migration so Aircraft exists.
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='WBConfig',
            fields=[
                ('id', models.UUIDField(
                    default=uuid.uuid4, editable=False, primary_key=True, serialize=False,
                )),
                ('empty_weight', models.DecimalField(
                    decimal_places=1, help_text='Basic empty weight in pounds', max_digits=8,
                )),
                ('empty_cg', models.DecimalField(
                    decimal_places=2, help_text='Empty CG — inches aft of datum', max_digits=7,
                )),
                ('max_gross_weight', models.DecimalField(
                    decimal_places=1, help_text='Maximum gross weight in pounds', max_digits=8,
                )),
                ('fwd_cg_limit', models.DecimalField(
                    decimal_places=2, help_text='Forward CG limit — inches aft of datum', max_digits=7,
                )),
                ('aft_cg_limit', models.DecimalField(
                    decimal_places=2, help_text='Aft CG limit — inches aft of datum', max_digits=7,
                )),
                ('stations', models.JSONField(
                    default=list, help_text='List of {name, arm} station dicts ordered for display',
                )),
                ('notes', models.TextField(blank=True)),
                ('aircraft', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='wb_config',
                    to='core.aircraft',
                )),
            ],
            options={
                'verbose_name': 'W&B configuration',
            },
        ),
        migrations.CreateModel(
            name='WBCalculation',
            fields=[
                ('id', models.UUIDField(
                    default=uuid.uuid4, editable=False, primary_key=True, serialize=False,
                )),
                ('label', models.CharField(
                    help_text="Short description, e.g. 'Solo cross-country' or 'Full fuel + 3 pax'",
                    max_length=200,
                )),
                ('items', models.JSONField(default=list)),
                ('empty_weight', models.DecimalField(decimal_places=1, max_digits=8)),
                ('empty_cg', models.DecimalField(decimal_places=2, max_digits=7)),
                ('gross_weight', models.DecimalField(decimal_places=1, max_digits=8)),
                ('gross_moment', models.DecimalField(decimal_places=2, max_digits=14)),
                ('gross_cg', models.DecimalField(decimal_places=2, max_digits=7)),
                ('within_limits', models.BooleanField()),
                ('notes', models.TextField(blank=True)),
                ('calculated_at', models.DateTimeField(auto_now_add=True)),
                ('aircraft', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='wb_calculations',
                    to='core.aircraft',
                )),
            ],
            options={
                'verbose_name': 'W&B calculation',
                'ordering': ['-calculated_at'],
            },
        ),
    ]
