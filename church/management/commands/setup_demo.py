"""
=================================================================
COMMANDE setup_demo — Crée les données de démonstration
=================================================================
Usage : python manage.py setup_demo

Cette commande crée :
- Un super-utilisateur admin (login: admin / mdp: admin123)
- Une église de démonstration avec toutes ses données
- Des événements, prédications, membres et pages de test
=================================================================
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from church.models import Church, ChurchMembership, Event, Sermon, Member, Page
from datetime import date, timedelta


class Command(BaseCommand):
    help = "Crée les données de démonstration pour tester la plateforme"

    def handle(self, *args, **options):
        # 1. Créer le super-utilisateur
        User = get_user_model()
        if not User.objects.filter(username='admin').exists():
            user = User.objects.create_superuser(
                username='admin',
                email='admin@eglise-demo.com',
                password='admin123',
                first_name='Admin',
                last_name='Principal',
            )
            self.stdout.write(self.style.SUCCESS('[OK] Super-utilisateur cree : admin / admin123'))
        else:
            user = User.objects.get(username='admin')
            self.stdout.write('[INFO] Super-utilisateur "admin" existe deja')

        # 2. Créer l'église de démonstration
        church, created = Church.objects.get_or_create(
            slug='demo',
            defaults={
                'name': 'Église de la Grâce',
                'description': 'Une communauté de foi vivante, engagée dans l\'amour et le service.',
                'address': '123 Avenue de la Paix',
                'city': 'Kinshasa',
                'country': 'RD Congo',
                'phone': '+243 812 345 678',
                'email': 'contact@eglise-grace.com',
                'primary_color': '#1a5276',
                'secondary_color': '#e74c3c',
                'welcome_message': 'Bienvenue dans la maison du Seigneur ! Nous sommes une famille unie par la foi et l\'amour de Dieu.',
                'service_times': 'Dimanche : 09h00 - 12h00\nMercredi : 18h00 - 20h00\nVendredi : 18h00 - 20h00 (Veillée de prière)',
                'pastor_name': 'Pasteur Jean-Baptiste Mukendi',
            }
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

        # 3. Créer des événements
        today = date.today()
        events_data = [
            {
                'title': 'Culte d\'actions de grâce',
                'description': 'Venez rendre grâce au Seigneur pour ses bienfaits durant ce mois.',
                'event_date': today + timedelta(days=7),
                'event_time': '09:00',
                'location': 'Temple principal',
                'is_featured': True,
            },
            {
                'title': 'Séminaire de formation des leaders',
                'description': 'Formation intensive pour les responsables de cellules de maison.',
                'event_date': today + timedelta(days=14),
                'event_time': '14:00',
                'location': 'Salle de conférence',
            },
            {
                'title': 'Concert de louange',
                'description': 'Une soirée de louange et d\'adoration avec le groupe Hosanna.',
                'event_date': today + timedelta(days=21),
                'event_time': '18:00',
                'location': 'Temple principal',
                'is_featured': True,
            },
        ]
        for ev_data in events_data:
            Event.objects.get_or_create(
                church=church,
                title=ev_data['title'],
                defaults=ev_data,
            )
        self.stdout.write(self.style.SUCCESS(f'[OK] {len(events_data)} evenements crees'))

        # 4. Créer des prédications
        sermons_data = [
            {
                'title': 'La puissance de la foi',
                'preacher': 'Pasteur Jean-Baptiste Mukendi',
                'description': 'Un message puissant sur la foi qui déplace les montagnes et transforme les situations impossibles.',
                'sermon_date': today,
                'bible_reference': 'Hébreux 11:1',
                'is_featured': True,
            },
            {
                'title': 'L\'amour inconditionnel de Dieu',
                'preacher': 'Pasteur Jean-Baptiste Mukendi',
                'description': 'Découvrez la profondeur de l\'amour de Dieu qui surpasse toute connaissance.',
                'sermon_date': today - timedelta(days=7),
                'bible_reference': 'Jean 3:16',
            },
            {
                'title': 'Marcher dans la victoire',
                'preacher': 'Évangéliste Marie Kabongo',
                'description': 'Nous sommes plus que vainqueurs par celui qui nous a aimés.',
                'sermon_date': today - timedelta(days=14),
                'bible_reference': 'Romains 8:37',
            },
        ]
        for s_data in sermons_data:
            Sermon.objects.get_or_create(
                church=church,
                title=s_data['title'],
                defaults=s_data,
            )
        self.stdout.write(self.style.SUCCESS(f'[OK] {len(sermons_data)} predications creees'))

        # 5. Créer des membres
        members_data = [
            {'first_name': 'Jean', 'last_name': 'Kabila', 'phone': '+243 810 000 001', 'gender': 'M', 'department': 'Louange'},
            {'first_name': 'Marie', 'last_name': 'Tshisekedi', 'phone': '+243 810 000 002', 'gender': 'F', 'department': 'Intercession'},
            {'first_name': 'Pierre', 'last_name': 'Mukeba', 'phone': '+243 810 000 003', 'gender': 'M', 'department': 'Protocole'},
            {'first_name': 'Grâce', 'last_name': 'Mwamba', 'phone': '+243 810 000 004', 'gender': 'F', 'department': 'École du dimanche'},
            {'first_name': 'David', 'last_name': 'Kasongo', 'phone': '+243 810 000 005', 'gender': 'M', 'department': 'Jeunesse'},
        ]
        for m_data in members_data:
            Member.objects.get_or_create(
                church=church,
                first_name=m_data['first_name'],
                last_name=m_data['last_name'],
                defaults={**m_data, 'membership_date': today - timedelta(days=365)},
            )
        self.stdout.write(self.style.SUCCESS(f'[OK] {len(members_data)} membres crees'))

        # 6. Créer des pages
        pages_data = [
            {
                'title': 'À propos',
                'slug': 'a-propos',
                'content': '<h2>Notre Histoire</h2><p>Fondée en 2010, notre église est née d\'une vision : rassembler les croyants dans l\'amour et la foi pour impacter notre communauté.</p><h2>Notre Vision</h2><p>Être une communauté de foi vivante, engagée dans la transformation spirituelle et sociale de notre ville.</p><h2>Nos Valeurs</h2><ul><li><strong>La Prière</strong> — Le fondement de tout ce que nous faisons</li><li><strong>L\'Amour</strong> — Aimer Dieu et aimer notre prochain</li><li><strong>Le Service</strong> — Servir avec joie et humilité</li><li><strong>L\'Excellence</strong> — Donner le meilleur au Seigneur</li></ul>',
                'sort_order': 1,
            },
            {
                'title': 'Nos Ministères',
                'slug': 'ministeres',
                'content': '<h2>Nos Ministères</h2><p>Chaque membre peut s\'épanouir dans le ministère qui correspond à ses dons.</p><h3>🎵 Louange et Adoration</h3><p>Notre équipe de louange conduit l\'assemblée dans la présence de Dieu chaque dimanche.</p><h3>📖 École du Dimanche</h3><p>Formation biblique pour enfants et adultes chaque dimanche matin.</p><h3>👥 Cellules de Maison</h3><p>Des petits groupes qui se réunissent dans les quartiers pour la prière et le partage.</p><h3>🤝 Action Sociale</h3><p>Aide aux démunis, visites aux malades, soutien scolaire.</p>',
                'sort_order': 2,
            },
        ]
        for p_data in pages_data:
            Page.objects.get_or_create(
                church=church,
                slug=p_data['slug'],
                defaults=p_data,
            )
        self.stdout.write(self.style.SUCCESS(f'[OK] {len(pages_data)} pages creees'))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=== Installation terminee ! ==='))
        self.stdout.write(f'   Acces admin : http://localhost:8000/admin/')
        self.stdout.write(f'   Login : admin / admin123')
        self.stdout.write(f'   Site public : http://localhost:8000/eglise/demo/')
        self.stdout.write(f'   Dashboard : http://localhost:8000/dashboard/')
