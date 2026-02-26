"""
=================================================================
URLS — Table de routage de l'application church
=================================================================
Ce fichier fait le lien entre les URLs et les vues (fonctions).
Quand un utilisateur tape une URL, Django cherche ici quelle 
fonction appeler.

STRUCTURE DES URLS :
- /                          → Page d'accueil globale
- /eglise/<slug>/            → Page d'accueil d'une église
- /eglise/<slug>/evenements/ → Événements de cette église
- /dashboard/                → Tableau de bord admin
- /dashboard/evenements/     → Gestion des événements
=================================================================
"""

from django.urls import path
from . import views

urlpatterns = [
    # === PAGES PUBLIQUES ===
    path('', views.home, name='home'),
    path('eglise/<slug:church_slug>/', views.church_home, name='church_home'),
    path('eglise/<slug:church_slug>/evenements/', views.church_events, name='church_events'),
    path('eglise/<slug:church_slug>/predications/', views.church_sermons, name='church_sermons'),
    path('eglise/<slug:church_slug>/contact/', views.church_contact, name='church_contact'),
    path('eglise/<slug:church_slug>/page/<slug:page_slug>/', views.church_page, name='church_page'),

    # === DASHBOARD (administration) ===
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/parametres/', views.church_settings, name='church_settings'),

    # Événements
    path('dashboard/evenements/', views.manage_events, name='manage_events'),
    path('dashboard/evenements/ajouter/', views.add_event, name='add_event'),
    path('dashboard/evenements/<int:pk>/modifier/', views.edit_event, name='edit_event'),
    path('dashboard/evenements/<int:pk>/supprimer/', views.delete_event, name='delete_event'),

    # Prédications
    path('dashboard/predications/', views.manage_sermons, name='manage_sermons'),
    path('dashboard/predications/ajouter/', views.add_sermon, name='add_sermon'),
    path('dashboard/predications/<int:pk>/modifier/', views.edit_sermon, name='edit_sermon'),
    path('dashboard/predications/<int:pk>/supprimer/', views.delete_sermon, name='delete_sermon'),

    # Membres
    path('dashboard/membres/', views.manage_members, name='manage_members'),
    path('dashboard/membres/ajouter/', views.add_member, name='add_member'),
    path('dashboard/membres/<int:pk>/modifier/', views.edit_member, name='edit_member'),
    path('dashboard/membres/<int:pk>/supprimer/', views.delete_member, name='delete_member'),

    # Messages
    path('dashboard/messages/', views.manage_messages, name='manage_messages'),
    path('dashboard/messages/<int:pk>/', views.read_message, name='read_message'),

    # Paramètres globaux (super-admin)
    path('dashboard/site/', views.site_settings, name='site_settings'),
]
