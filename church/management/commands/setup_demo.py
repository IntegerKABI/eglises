"""Create demo data for local development and manual smoke tests."""

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from church.models import Church, ChurchMembership, Event, Member, Page, Sermon


class Command(BaseCommand):
    help = "Create demo data for local development and smoke testing."

    def handle(self, *args, **options):
        user_model = get_user_model()
        if not user_model.objects.filter(username='admin').exists():
            user = user_model.objects.create_superuser(
                username='admin',
                email='admin@eglise-demo.com',
                password='admin123',
                first_name='Admin',
                last_name='Principal',
            )
            self.stdout.write(self.style.SUCCESS('[OK] Super-utilisateur cree : admin / admin123'))
        else:
            user = user_model.objects.get(username='admin')
            self.stdout.write('[INFO] Super-utilisateur "admin" existe deja')

        church, created = Church.objects.get_or_create(
            slug='demo',
            defaults={
                'name': 'Eglise de la Grace',
                'description': "Une communaute de foi vivante, engagee dans l'amour et le service.",
                'address': '123 Avenue de la Paix',
                'city': 'Kinshasa',
                'country': 'RD Congo',
                'phone': '+243 812 345 678',
                'email': 'contact@eglise-grace.com',
                'primary_color': '#1a5276',
                'secondary_color': '#e74c3c',
                'welcome_message': "Bienvenue dans la maison du Seigneur ! Nous sommes une famille unie par la foi et l'amour de Dieu.",
                'service_times': 'Dimanche : 09h00 - 12h00\nMercredi : 18h00 - 20h00\nVendredi : 18h00 - 20h00 (Veillee de priere)',
                'pastor_name': 'Pasteur Jean-Baptiste Mukendi',
            },
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'[OK] Eglise creee : {church.name}'))
        else:
            self.stdout.write(f'[INFO] Eglise "{church.name}" existe deja')

        ChurchMembership.objects.get_or_create(
            user=user,
            church=church,
            defaults={'role': ChurchMembership.Role.ADMIN, 'is_active': True},
        )

        today = date.today()
        events_data = [
            {
                'title': "Culte d'actions de grace",
                'description': 'Venez rendre grace au Seigneur pour ses bienfaits durant ce mois.',
                'event_date': today + timedelta(days=7),
                'event_time': '09:00',
                'location': 'Temple principal',
                'is_featured': True,
            },
            {
                'title': 'Seminaire de formation des leaders',
                'description': 'Une journee de formation et de communion pour les responsables des ministeres.',
                'event_date': today + timedelta(days=14),
                'event_time': '10:00',
                'location': 'Salle polyvalente',
            },
            {
                'title': 'Veillee de priere',
                'description': 'Une nuit entiere de priere, d\'intercession et d\'adoration.',
                'event_date': today + timedelta(days=21),
                'event_time': '22:00',
                'location': 'Temple principal',
            },
        ]
        for event_data in events_data:
            Event.objects.get_or_create(church=church, title=event_data['title'], defaults=event_data)

        sermons_data = [
            {
                'title': 'La foi qui deplace les montagnes',
                'preacher': 'Pasteur Jean-Baptiste Mukendi',
                'description': 'Un message sur la puissance de la foi en Christ.',
                'sermon_date': today - timedelta(days=7),
                'bible_reference': 'Matthieu 17:20',
                'video_url': 'https://www.youtube.com/watch?v=example1',
            },
            {
                'title': "L'amour du prochain",
                'preacher': 'Pasteur Marie Kanku',
                'description': 'Un enseignement sur la compassion, la misericorde et le service.',
                'sermon_date': today - timedelta(days=14),
                'bible_reference': 'Luc 10:27',
            },
            {
                'title': 'Marcher dans la paix de Dieu',
                'preacher': 'Pasteur Samuel Ilunga',
                'description': 'Un rappel a vivre dans la paix que Dieu donne a son peuple.',
                'sermon_date': today - timedelta(days=21),
                'bible_reference': 'Philippiens 4:7',
            },
        ]
        for sermon_data in sermons_data:
            Sermon.objects.get_or_create(church=church, title=sermon_data['title'], defaults=sermon_data)

        members_data = [
            {
                'first_name': 'Grace',
                'last_name': 'Mutombo',
                'phone': '+243 812 000 001',
                'email': 'grace.mutombo@example.com',
                'department': 'Chorale',
            },
            {
                'first_name': 'Samuel',
                'last_name': 'Banza',
                'phone': '+243 812 000 002',
                'email': 'samuel.banza@example.com',
                'department': 'Protocole',
            },
            {
                'first_name': 'Esther',
                'last_name': 'Kalala',
                'phone': '+243 812 000 003',
                'email': 'esther.kalala@example.com',
                'department': 'Intercession',
            },
            {
                'first_name': 'Daniel',
                'last_name': 'Mbuyi',
                'phone': '+243 812 000 004',
                'email': 'daniel.mbuyi@example.com',
                'department': 'Media',
            },
            {
                'first_name': 'Rachel',
                'last_name': 'Mwamba',
                'phone': '+243 812 000 005',
                'email': 'rachel.mwamba@example.com',
                'department': 'Accueil',
            },
        ]
        for member_data in members_data:
            Member.objects.get_or_create(
                church=church,
                first_name=member_data['first_name'],
                last_name=member_data['last_name'],
                defaults=member_data,
            )

        pages_data = [
            {
                'title': 'Notre Histoire',
                'content': "<h2>Notre Histoire</h2><p>Fondee en 2010, notre eglise est nee d'une vision : rassembler les croyants dans l'amour et la foi pour impacter notre communaute.</p><h2>Notre Vision</h2><p>Etre une communaute de foi vivante, engagee dans la transformation spirituelle et sociale de notre ville.</p><h2>Nos Valeurs</h2><ul><li><strong>La Priere</strong> - Le fondement de tout ce que nous faisons</li><li><strong>L'Amour</strong> - Aimer Dieu et aimer notre prochain</li><li><strong>Le Service</strong> - Servir avec joie et humilite</li><li><strong>L'Excellence</strong> - Donner le meilleur au Seigneur</li></ul>",
                'sort_order': 1,
                'is_in_menu': True,
            },
            {
                'title': 'Ministeres',
                'content': '<p>Decouvrez les differents ministeres de notre assemblee.</p>',
                'sort_order': 2,
                'is_in_menu': True,
            },
        ]
        for page_data in pages_data:
            Page.objects.get_or_create(church=church, title=page_data['title'], defaults=page_data)

        self.stdout.write(self.style.SUCCESS('\nInstallation terminee.'))
        self.stdout.write('   Admin login  : admin / admin123')
        self.stdout.write('   Site public  : http://localhost:8000/eglise/demo/')
        self.stdout.write('   Dashboard    : http://localhost:8000/dashboard/')
