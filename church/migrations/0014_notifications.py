from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("church", "0013_member_privacy_consent"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Notification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("category", models.CharField(choices=[("invite", "Invitation"), ("role", "Changement de rôle"), ("message", "Nouveau message"), ("event", "Changement événement"), ("sermon", "Changement prédication")], db_index=True, max_length=20, verbose_name="Catégorie")),
                ("title", models.CharField(max_length=255, verbose_name="Titre")),
                ("body", models.TextField(blank=True, verbose_name="Message")),
                ("link", models.CharField(blank=True, max_length=300, verbose_name="Lien")),
                ("is_read", models.BooleanField(db_index=True, default=False, verbose_name="Lu")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("church", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="notifications", to="church.church", verbose_name="Église")),
                ("recipient", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="notifications", to=settings.AUTH_USER_MODEL, verbose_name="Destinataire")),
            ],
            options={
                "verbose_name": "Notification",
                "verbose_name_plural": "Notifications",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(fields=["recipient", "is_read", "created_at"], name="notif_rec_read_cr_idx"),
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(fields=["church", "created_at"], name="notif_ch_cr_idx"),
        ),
    ]
