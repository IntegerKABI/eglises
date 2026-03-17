from django.conf import settings
from django.db import migrations, models


def set_status_from_is_read(apps, schema_editor):
    ContactMessage = apps.get_model("church", "ContactMessage")
    ContactMessage.objects.filter(is_read=True).update(status="read")


class Migration(migrations.Migration):
    dependencies = [
        ("church", "0011_event_sermon_slug"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="contactmessage",
            name="status",
            field=models.CharField(choices=[("new", "Nouveau"), ("read", "Lu"), ("responded", "Répondu"), ("archived", "Archivé")], db_index=True, default="new", max_length=20, verbose_name="Statut"),
        ),
        migrations.AddField(
            model_name="contactmessage",
            name="assigned_to",
            field=models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name="assigned_contact_messages", to=settings.AUTH_USER_MODEL, verbose_name="Assigné à"),
        ),
        migrations.AddField(
            model_name="contactmessage",
            name="responded_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Répondu le"),
        ),
        migrations.AddField(
            model_name="contactmessage",
            name="responded_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name="responded_contact_messages", to=settings.AUTH_USER_MODEL, verbose_name="Répondu par"),
        ),
        migrations.AddField(
            model_name="contactmessage",
            name="archived_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Archivé le"),
        ),
        migrations.RunPython(set_status_from_is_read, migrations.RunPython.noop),
        migrations.CreateModel(
            name="ContactMessageReply",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("body", models.TextField(verbose_name="Réponse")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name="contact_message_replies", to=settings.AUTH_USER_MODEL, verbose_name="Répondu par")),
                ("message", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="replies", to="church.contactmessage", verbose_name="Message")),
            ],
            options={
                "verbose_name": "Réponse au message",
                "verbose_name_plural": "Réponses aux messages",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="contactmessage",
            index=models.Index(fields=["church", "status", "created_at"], name="cm_ch_stat_cr_idx"),
        ),
        migrations.AddIndex(
            model_name="contactmessage",
            index=models.Index(fields=["assigned_to", "status"], name="cm_asg_stat_idx"),
        ),
        migrations.AddIndex(
            model_name="contactmessagereply",
            index=models.Index(fields=["message", "created_at"], name="cmr_msg_cr_idx"),
        ),
    ]
