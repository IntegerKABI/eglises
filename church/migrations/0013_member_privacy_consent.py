from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("church", "0012_contact_message_workflow"),
    ]

    operations = [
        migrations.AddField(
            model_name="member",
            name="directory_consent",
            field=models.BooleanField(default=False, help_text="Autorise l'affichage dans l'annuaire public.", verbose_name="Consentement annuaire"),
        ),
        migrations.AddField(
            model_name="member",
            name="directory_consent_source",
            field=models.CharField(blank=True, max_length=255, verbose_name="Source du consentement"),
        ),
        migrations.AddField(
            model_name="member",
            name="directory_consent_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Consentement donné le"),
        ),
        migrations.AddIndex(
            model_name="member",
            index=models.Index(fields=["church", "directory_consent"], name="member_ch_cons_idx"),
        ),
    ]
