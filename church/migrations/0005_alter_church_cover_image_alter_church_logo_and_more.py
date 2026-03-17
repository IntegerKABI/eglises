import church.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('church', '0004_alter_church_is_active_alter_event_event_date_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='church',
            name='cover_image',
            field=models.ImageField(blank=True, null=True, upload_to=church.models.upload_church_cover, verbose_name='Image de couverture'),
        ),
        migrations.AlterField(
            model_name='church',
            name='logo',
            field=models.ImageField(blank=True, null=True, upload_to=church.models.upload_church_logo, verbose_name='Logo'),
        ),
        migrations.AlterField(
            model_name='event',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to=church.models.upload_event_image, verbose_name='Image'),
        ),
        migrations.AlterField(
            model_name='member',
            name='photo',
            field=models.ImageField(blank=True, null=True, upload_to=church.models.upload_member_photo, verbose_name='Photo'),
        ),
        migrations.AlterField(
            model_name='page',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to=church.models.upload_page_image, verbose_name='Image'),
        ),
        migrations.AlterField(
            model_name='sermon',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to=church.models.upload_sermon_image, verbose_name='Image'),
        ),
        migrations.AlterField(
            model_name='sitesettings',
            name='cover_image',
            field=models.ImageField(blank=True, help_text="Affichée en arrière-plan sur la page d'accueil", null=True, upload_to=church.models.upload_site_asset, verbose_name='Image de couverture'),
        ),
        migrations.AlterField(
            model_name='sitesettings',
            name='site_logo',
            field=models.ImageField(blank=True, null=True, upload_to=church.models.upload_site_asset, verbose_name='Logo de la plateforme'),
        ),
    ]
