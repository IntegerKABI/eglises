from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("church", "0017_alter_church_options_alter_churchinvitation_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="churchinvitation",
            name="declined_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="churchinvitation",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "En attente"),
                    ("accepted", "AcceptÃ©e"),
                    ("declined", "RefusÃ©e"),
                    ("revoked", "RÃ©voquÃ©e"),
                    ("expired", "ExpirÃ©e"),
                ],
                db_index=True,
                default="pending",
                max_length=20,
                verbose_name="Statut",
            ),
        ),
    ]
