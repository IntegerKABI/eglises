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
    path('invite/<uuid:token>/', views.accept_invite, name='accept_invite'),
    path('invitations/', views.pending_invitations, name='pending_invitations'),
    path('invite/<uuid:token>/decline/', views.decline_invite, name='decline_invite'),

    # === DASHBOARD (administration) ===
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/selection/', views.select_church, name='select_church'),
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

    # Pages
    path('dashboard/pages/', views.manage_pages, name='manage_pages'),
    path('dashboard/pages/ajouter/', views.add_page, name='add_page'),
    path('dashboard/pages/<int:pk>/modifier/', views.edit_page, name='edit_page'),
    path('dashboard/pages/<int:pk>/supprimer/', views.delete_page, name='delete_page'),

    # Messages
    path('dashboard/messages/', views.manage_messages, name='manage_messages'),
    path('dashboard/messages/<int:pk>/', views.read_message, name='read_message'),

    # Notifications
    path('dashboard/notifications/', views.manage_notifications, name='manage_notifications'),
    path('dashboard/notifications/<int:pk>/open/', views.open_notification, name='open_notification'),
    path('dashboard/notifications/<int:pk>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('dashboard/notifications/read-all/', views.mark_all_notifications_read, name='mark_all_notifications_read'),

    # Audit
    path('dashboard/audit/', views.manage_audit_logs, name='manage_audit_logs'),

    # Utilisateurs
    path('dashboard/utilisateurs/', views.manage_users, name='manage_users'),
    path('dashboard/utilisateurs/ajouter/', views.add_user, name='add_user'),
    path('dashboard/utilisateurs/assigner/', views.assign_user, name='assign_user'),
    path('dashboard/utilisateurs/inviter/', views.invite_user, name='invite_user'),
    path('dashboard/utilisateurs/transferer/', views.transfer_admin, name='transfer_admin'),
    path('dashboard/utilisateurs/<int:pk>/modifier/', views.edit_membership, name='edit_membership'),
    path('dashboard/utilisateurs/<int:pk>/toggle/', views.toggle_membership, name='toggle_membership'),
    path('dashboard/invitations/<int:pk>/revoquer/', views.revoke_invite, name='revoke_invite'),
    path('dashboard/invitations/<int:pk>/renvoyer/', views.resend_invite, name='resend_invite'),

    # Paramètres globaux (super-admin)
    path('dashboard/site/', views.site_settings, name='site_settings'),
    path('dashboard/platform/churches/', views.superadmin_church_list, name='superadmin_church_list'),
    path('dashboard/platform/churches/create/', views.superadmin_church_create, name='superadmin_church_create'),
    path('dashboard/platform/churches/<int:pk>/', views.superadmin_church_detail, name='superadmin_church_detail'),
    path('dashboard/platform/churches/<int:pk>/edit/', views.superadmin_church_edit, name='superadmin_church_edit'),
    path('dashboard/platform/churches/<int:pk>/status/', views.superadmin_church_status, name='superadmin_church_status'),
    path('dashboard/platform/churches/<int:pk>/plan/', views.superadmin_church_plan, name='superadmin_church_plan'),
    path('dashboard/platform/churches/<int:pk>/switch/', views.superadmin_switch_church, name='superadmin_switch_church'),
]
