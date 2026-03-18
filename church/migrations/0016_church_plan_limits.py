from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("church", "0015_audit_log"),
    ]

    operations = [
        migrations.AddField(
            model_name="church",
            name="plan",
            field=models.CharField(
                choices=[("starter", "Starter"), ("growth", "Growth"), ("scale", "Scale")],
                db_index=True,
                default="starter",
                max_length=20,
                verbose_name="Plan",
            ),
        ),
        migrations.AddField(
            model_name="church",
            name="max_members_override",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Laissez vide pour utiliser la limite du plan.",
                null=True,
                verbose_name="Limite membres personnalisee",
            ),
        ),
        migrations.AddField(
            model_name="church",
            name="max_events_override",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Laissez vide pour utiliser la limite du plan.",
                null=True,
                verbose_name="Limite evenements personnalisee",
            ),
        ),
        migrations.AddField(
            model_name="church",
            name="max_storage_mb_override",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Laissez vide pour utiliser la limite du plan.",
                null=True,
                verbose_name="Limite stockage personnalisee (Mo)",
            ),
        ),
    ]
