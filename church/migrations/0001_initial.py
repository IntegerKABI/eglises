import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Church',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name="Nom de l'église")),
                ('slug', models.SlugField(help_text="Généré automatiquement à partir du nom. Ex: 'vie-nouvelle'", max_length=100, unique=True, verbose_name='Identifiant URL')),
                ('description', models.TextField(blank=True, verbose_name='Description')),
                ('logo', models.ImageField(blank=True, null=True, upload_to='churches/logos/', verbose_name='Logo')),
                ('cover_image', models.ImageField(blank=True, null=True, upload_to='churches/covers/', verbose_name='Image de couverture')),
                ('address', models.CharField(blank=True, max_length=500, verbose_name='Adresse')),
                ('city', models.CharField(blank=True, max_length=100, verbose_name='Ville')),
                ('country', models.CharField(default='RD Congo', max_length=100, verbose_name='Pays')),
                ('phone', models.CharField(blank=True, max_length=50, verbose_name='Téléphone')),
                ('email', models.EmailField(blank=True, max_length=254, verbose_name='Email')),
                ('facebook', models.URLField(blank=True, verbose_name='Facebook')),
                ('youtube', models.URLField(blank=True, verbose_name='YouTube')),
                ('instagram', models.URLField(blank=True, verbose_name='Instagram')),
                ('primary_color', models.CharField(default='#2c3e50', help_text='Code hexadécimal, ex: #2c3e50', max_length=7, verbose_name='Couleur principale')),
                ('secondary_color', models.CharField(default='#3498db', max_length=7, verbose_name='Couleur secondaire')),
                ('welcome_message', models.TextField(blank=True, help_text="Affiché sur la page d'accueil", verbose_name="Message d'accueil")),
                ('service_times', models.TextField(blank=True, help_text='Ex: Dimanche 09h-12h, Mercredi 18h-20h', verbose_name='Horaires des cultes')),
                ('pastor_name', models.CharField(blank=True, max_length=150, verbose_name='Nom du pasteur')),
                ('is_active', models.BooleanField(default=True, verbose_name='Active')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('admin', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='churches', to=settings.AUTH_USER_MODEL, verbose_name='Administrateur')),
            ],
            options={
                'verbose_name': 'Église',
                'verbose_name_plural': 'Églises',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='ContactMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sender_name', models.CharField(max_length=150, verbose_name='Nom')),
                ('sender_email', models.EmailField(max_length=254, verbose_name='Email')),
                ('subject', models.CharField(blank=True, max_length=255, verbose_name='Sujet')),
                ('message', models.TextField(verbose_name='Message')),
                ('is_read', models.BooleanField(default=False, verbose_name='Lu')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('church', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='church.church', verbose_name='Église')),
            ],
            options={
                'verbose_name': 'Message de contact',
                'verbose_name_plural': 'Messages de contact',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Event',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255, verbose_name='Titre')),
                ('description', models.TextField(blank=True, verbose_name='Description')),
                ('image', models.ImageField(blank=True, null=True, upload_to='events/', verbose_name='Image')),
                ('event_date', models.DateField(verbose_name='Date')),
                ('event_time', models.TimeField(blank=True, null=True, verbose_name='Heure')),
                ('end_date', models.DateField(blank=True, null=True, verbose_name='Date de fin')),
                ('location', models.CharField(blank=True, max_length=255, verbose_name='Lieu')),
                ('is_featured', models.BooleanField(default=False, verbose_name='Mis en avant')),
                ('is_active', models.BooleanField(default=True, verbose_name='Actif')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('church', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='events', to='church.church', verbose_name='Église')),
            ],
            options={
                'verbose_name': 'Événement',
                'verbose_name_plural': 'Événements',
                'ordering': ['-event_date'],
            },
        ),
        migrations.CreateModel(
            name='Member',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('first_name', models.CharField(max_length=100, verbose_name='Prénom')),
                ('last_name', models.CharField(max_length=100, verbose_name='Nom')),
                ('email', models.EmailField(blank=True, max_length=254, verbose_name='Email')),
                ('phone', models.CharField(blank=True, max_length=50, verbose_name='Téléphone')),
                ('address', models.CharField(blank=True, max_length=500, verbose_name='Adresse')),
                ('birth_date', models.DateField(blank=True, null=True, verbose_name='Date de naissance')),
                ('gender', models.CharField(blank=True, choices=[('M', 'Masculin'), ('F', 'Féminin')], max_length=1, verbose_name='Genre')),
                ('membership_date', models.DateField(blank=True, null=True, verbose_name="Date d'adhésion")),
                ('department', models.CharField(blank=True, max_length=100, verbose_name='Département/Ministère')),
                ('photo', models.ImageField(blank=True, null=True, upload_to='members/', verbose_name='Photo')),
                ('is_active', models.BooleanField(default=True, verbose_name='Actif')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('church', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='members', to='church.church', verbose_name='Église')),
            ],
            options={
                'verbose_name': 'Membre',
                'verbose_name_plural': 'Membres',
                'ordering': ['last_name', 'first_name'],
            },
        ),
        migrations.CreateModel(
            name='Sermon',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255, verbose_name='Titre')),
                ('preacher', models.CharField(blank=True, max_length=150, verbose_name='Prédicateur')),
                ('description', models.TextField(blank=True, verbose_name='Description')),
                ('image', models.ImageField(blank=True, null=True, upload_to='sermons/', verbose_name='Image')),
                ('video_url', models.URLField(blank=True, verbose_name='Lien vidéo (YouTube)')),
                ('audio_url', models.URLField(blank=True, verbose_name='Lien audio')),
                ('sermon_date', models.DateField(blank=True, null=True, verbose_name='Date')),
                ('bible_reference', models.CharField(blank=True, help_text='Ex: Jean 3:16', max_length=255, verbose_name='Référence biblique')),
                ('is_featured', models.BooleanField(default=False, verbose_name='Mis en avant')),
                ('is_active', models.BooleanField(default=True, verbose_name='Actif')),
                ('views_count', models.PositiveIntegerField(default=0, verbose_name='Nombre de vues')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('church', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sermons', to='church.church', verbose_name='Église')),
            ],
            options={
                'verbose_name': 'Prédication',
                'verbose_name_plural': 'Prédications',
                'ordering': ['-sermon_date'],
            },
        ),
        migrations.CreateModel(
            name='Page',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255, verbose_name='Titre')),
                ('slug', models.SlugField(max_length=100, verbose_name='Identifiant URL')),
                ('content', models.TextField(blank=True, verbose_name='Contenu')),
                ('image', models.ImageField(blank=True, null=True, upload_to='pages/', verbose_name='Image')),
                ('sort_order', models.IntegerField(default=0, verbose_name="Ordre d'affichage")),
                ('is_in_menu', models.BooleanField(default=True, verbose_name='Afficher dans le menu')),
                ('is_active', models.BooleanField(default=True, verbose_name='Active')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('church', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pages', to='church.church', verbose_name='Église')),
            ],
            options={
                'verbose_name': 'Page',
                'verbose_name_plural': 'Pages',
                'ordering': ['sort_order'],
                'unique_together': {('church', 'slug')},
            },
        ),
    ]
