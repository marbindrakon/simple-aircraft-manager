from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('health', '0021_documentcollection_starred'),
    ]

    operations = [
        migrations.AddField(
            model_name='majorrepairalteration',
            name='has_ica',
            field=models.BooleanField(default=False, help_text='This record includes Instructions for Continued Airworthiness (ICAs)'),
        ),
        migrations.AddField(
            model_name='majorrepairalteration',
            name='ica_notes',
            field=models.TextField(blank=True, help_text='Notes about where the ICAs are located and what they cover'),
        ),
    ]
