from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('church', '0002_sitesettings'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitesettings',
            name='cover_image',
            field=models.ImageField(blank=True, help_text="Affichée en arrière-plan sur la page d'accueil", null=True, upload_to='site/', verbose_name='Image de couverture'),
        ),
    ]
