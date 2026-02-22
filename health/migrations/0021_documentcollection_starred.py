from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('health', '0020_document_visibility'),
    ]

    operations = [
        migrations.AddField(
            model_name='documentcollection',
            name='starred',
            field=models.BooleanField(default=False),
        ),
    ]
