from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def set_visibility(apps, schema_editor):
    Event = apps.get_model('church', 'Event')
    Sermon = apps.get_model('church', 'Sermon')
    Page = apps.get_model('church', 'Page')

    Event.objects.filter(is_active=True).update(visibility='public')
    Event.objects.filter(is_active=False).update(visibility='draft')
    Sermon.objects.filter(is_active=True).update(visibility='public')
    Sermon.objects.filter(is_active=False).update(visibility='draft')
    Page.objects.filter(is_active=True).update(visibility='public')
    Page.objects.filter(is_active=False).update(visibility='draft')


class Migration(migrations.Migration):

    dependencies = [
        ('church', '0008_church_invitation'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_events', to=settings.AUTH_USER_MODEL, verbose_name='Créé par'),
        ),
        migrations.AddField(
            model_name='event',
            name='published_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Date de publication'),
        ),
        migrations.AddField(
            model_name='event',
            name='visibility',
            field=models.CharField(choices=[('public', 'Public'), ('private', 'Privé'), ('draft', 'Brouillon')], default='public', max_length=20, verbose_name='Visibilité'),
        ),
        migrations.AddField(
            model_name='sermon',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_sermons', to=settings.AUTH_USER_MODEL, verbose_name='Créé par'),
        ),
        migrations.AddField(
            model_name='sermon',
            name='published_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Date de publication'),
        ),
        migrations.AddField(
            model_name='sermon',
            name='visibility',
            field=models.CharField(choices=[('public', 'Public'), ('private', 'Privé'), ('draft', 'Brouillon')], default='public', max_length=20, verbose_name='Visibilité'),
        ),
        migrations.AddField(
            model_name='page',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_pages', to=settings.AUTH_USER_MODEL, verbose_name='Créé par'),
        ),
        migrations.AddField(
            model_name='page',
            name='published_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Date de publication'),
        ),
        migrations.AddField(
            model_name='page',
            name='visibility',
            field=models.CharField(choices=[('public', 'Public'), ('private', 'Privé'), ('draft', 'Brouillon')], default='public', max_length=20, verbose_name='Visibilité'),
        ),
        migrations.AddIndex(
            model_name='event',
            index=models.Index(fields=['church', 'visibility', 'published_at'], name='evt_ch_vis_pub_idx'),
        ),
        migrations.AddIndex(
            model_name='sermon',
            index=models.Index(fields=['church', 'visibility', 'published_at'], name='serm_ch_vis_pub_idx'),
        ),
        migrations.AddIndex(
            model_name='page',
            index=models.Index(fields=['church', 'visibility', 'published_at'], name='page_ch_vis_pub_idx'),
        ),
        migrations.RunPython(set_visibility, migrations.RunPython.noop),
    ]
