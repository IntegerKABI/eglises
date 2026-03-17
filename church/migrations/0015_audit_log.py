from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("church", "0014_notifications"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(db_index=True, max_length=50, verbose_name="Action")),
                ("object_type", models.CharField(db_index=True, max_length=100, verbose_name="Type d'objet")),
                ("object_id", models.CharField(blank=True, max_length=64, verbose_name="ID objet")),
                ("object_repr", models.CharField(blank=True, max_length=255, verbose_name="Résumé")),
                ("metadata", models.JSONField(blank=True, default=dict, verbose_name="Détails")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name="audit_logs", to=settings.AUTH_USER_MODEL, verbose_name="Auteur")),
                ("church", models.ForeignKey(blank=True, null=True, on_delete=models.deletion.CASCADE, related_name="audit_logs", to="church.church", verbose_name="Église")),
            ],
            options={
                "verbose_name": "Journal d'audit",
                "verbose_name_plural": "Journaux d'audit",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["church", "created_at"], name="audit_ch_cr_idx"),
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["actor", "created_at"], name="audit_actor_cr_idx"),
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["object_type", "object_id"], name="audit_obj_idx"),
        ),
    ]
