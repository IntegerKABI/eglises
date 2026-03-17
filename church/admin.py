"""
=================================================================
ADMIN — Configuration de l'interface d'administration Django
=================================================================
Ce fichier personnalise l'admin Django (/admin/) pour gérer 
facilement les églises, événements, prédications, etc.

Django génère automatiquement un back-office complet à partir 
de nos modèles. On le personnalise ici pour le rendre plus 
pratique (filtres, recherche, colonnes affichées, etc.)
=================================================================
"""

from django.contrib import admin
from .models import Church, ChurchInvitation, ChurchMembership, Event, Sermon, Member, Page, ContactMessage, SiteSettings


@admin.register(Church)
class ChurchAdmin(admin.ModelAdmin):
    list_display = ['name', 'city', 'email', 'status', 'created_at']
    list_filter = ['status', 'city', 'country']
    search_fields = ['name', 'city', 'email']
    prepopulated_fields = {'slug': ('name',)}
    exclude = ['is_active']


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['title', 'church', 'slug', 'event_date', 'visibility', 'published_at', 'created_by', 'is_featured', 'is_active']
    list_filter = ['church', 'visibility', 'is_featured', 'is_active', 'event_date']
    search_fields = ['title', 'description']
    prepopulated_fields = {'slug': ('title',)}


@admin.register(Sermon)
class SermonAdmin(admin.ModelAdmin):
    list_display = ['title', 'church', 'slug', 'preacher', 'sermon_date', 'visibility', 'published_at', 'created_by', 'views_count']
    list_filter = ['church', 'visibility', 'is_featured', 'is_active']
    search_fields = ['title', 'preacher', 'bible_reference']
    prepopulated_fields = {'slug': ('title',)}


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ['last_name', 'first_name', 'church', 'phone', 'department', 'is_active']
    list_filter = ['church', 'gender', 'department', 'is_active']
    search_fields = ['first_name', 'last_name', 'email', 'phone']


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ['title', 'church', 'slug', 'sort_order', 'is_in_menu', 'visibility', 'published_at', 'created_by', 'is_active']
    list_filter = ['church', 'is_in_menu', 'visibility', 'is_active']
    prepopulated_fields = {'slug': ('title',)}


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ['sender_name', 'sender_email', 'subject', 'church', 'is_read', 'created_at']
    list_filter = ['church', 'is_read']
    search_fields = ['sender_name', 'sender_email', 'subject', 'message']


@admin.register(ChurchMembership)
class ChurchMembershipAdmin(admin.ModelAdmin):
    list_display = ['user', 'church', 'role', 'is_active', 'created_at']
    list_filter = ['church', 'role', 'is_active']
    search_fields = ['user__username', 'user__email', 'user__first_name', 'user__last_name']


@admin.register(ChurchInvitation)
class ChurchInvitationAdmin(admin.ModelAdmin):
    list_display = ['email', 'church', 'role', 'status', 'created_at', 'expires_at']
    list_filter = ['church', 'role', 'status']
    search_fields = ['email']


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ['site_name', 'contact_email']
