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
from .models import Church, Event, Sermon, Member, Page, ContactMessage


@admin.register(Church)
class ChurchAdmin(admin.ModelAdmin):
    list_display = ['name', 'city', 'email', 'is_active', 'created_at']
    list_filter = ['is_active', 'city', 'country']
    search_fields = ['name', 'city', 'email']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['title', 'church', 'event_date', 'is_featured', 'is_active']
    list_filter = ['church', 'is_featured', 'is_active', 'event_date']
    search_fields = ['title', 'description']


@admin.register(Sermon)
class SermonAdmin(admin.ModelAdmin):
    list_display = ['title', 'church', 'preacher', 'sermon_date', 'views_count']
    list_filter = ['church', 'is_featured', 'is_active']
    search_fields = ['title', 'preacher', 'bible_reference']


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ['last_name', 'first_name', 'church', 'phone', 'department', 'is_active']
    list_filter = ['church', 'gender', 'department', 'is_active']
    search_fields = ['first_name', 'last_name', 'email', 'phone']


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ['title', 'church', 'slug', 'sort_order', 'is_in_menu', 'is_active']
    list_filter = ['church', 'is_in_menu', 'is_active']
    prepopulated_fields = {'slug': ('title',)}


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ['sender_name', 'sender_email', 'subject', 'church', 'is_read', 'created_at']
    list_filter = ['church', 'is_read']
    search_fields = ['sender_name', 'sender_email', 'subject', 'message']
