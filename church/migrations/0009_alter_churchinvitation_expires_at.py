import church.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('church', '0008_church_invitation'),
    ]

    operations = [
        migrations.AlterField(
            model_name='churchinvitation',
            name='expires_at',
            field=models.DateTimeField(default=church.models._default_invite_expiry),
        ),
    ]
