from django.db import migrations, models


def set_status_from_is_active(apps, schema_editor):
    Church = apps.get_model('church', 'Church')
    Church.objects.filter(is_active=True).update(status='active')
    Church.objects.filter(is_active=False).update(status='suspended')


class Migration(migrations.Migration):

    dependencies = [
        ('church', '0006_churchmembership_remove_admin'),
    ]

    operations = [
        migrations.AddField(
            model_name='church',
            name='status',
            field=models.CharField(
                choices=[
                    ('draft', 'Brouillon'),
                    ('active', 'Active'),
                    ('suspended', 'Suspendue'),
                    ('archived', 'Archivée'),
                ],
                db_index=True,
                default='active',
                max_length=20,
                verbose_name='Statut',
            ),
        ),
        migrations.RunPython(set_status_from_is_active, migrations.RunPython.noop),
    ]
