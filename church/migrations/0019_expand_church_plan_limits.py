from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("church", "0018_churchinvitation_declined_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="church",
            name="max_sermons_override",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Laissez vide pour utiliser la limite du plan.",
                null=True,
                verbose_name="Limite predications personnalisee",
            ),
        ),
        migrations.AddField(
            model_name="church",
            name="max_pages_override",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Laissez vide pour utiliser la limite du plan.",
                null=True,
                verbose_name="Limite pages personnalisee",
            ),
        ),
        migrations.AddField(
            model_name="church",
            name="max_users_override",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Laissez vide pour utiliser la limite du plan.",
                null=True,
                verbose_name="Limite utilisateurs personnalisee",
            ),
        ),
        migrations.AddField(
            model_name="church",
            name="max_pending_invitations_override",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Laissez vide pour utiliser la limite du plan.",
                null=True,
                verbose_name="Limite invitations en attente personnalisee",
            ),
        ),
        migrations.AddField(
            model_name="church",
            name="message_retention_days_override",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Laissez vide pour utiliser la retention du plan.",
                null=True,
                verbose_name="Retention messages personnalisee (jours)",
            ),
        ),
        migrations.AddField(
            model_name="church",
            name="notification_retention_days_override",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Laissez vide pour utiliser la retention du plan.",
                null=True,
                verbose_name="Retention notifications personnalisee (jours)",
            ),
        ),
    ]
