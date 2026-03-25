"""Django admin registrations for the church domain."""

from django.contrib import admin

from .models import (
    AuditLog,
    BackgroundJob,
    Church,
    ChurchInvitation,
    ChurchMembership,
    ContactMessage,
    ContactMessageReply,
    Event,
    Member,
    Notification,
    Page,
    Sermon,
    SiteSettings,
)


@admin.register(Church)
class ChurchAdmin(admin.ModelAdmin):
    """Manage tenant churches from the Django admin."""

    list_display = ['name', 'plan', 'city', 'email', 'status', 'created_at']
    list_filter = ['plan', 'status', 'city', 'country']
    search_fields = ['name', 'city', 'email']
    prepopulated_fields = {'slug': ('name',)}
    exclude = ['is_active']


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    """Manage church events from the Django admin."""

    list_display = ['title', 'church', 'slug', 'event_date', 'visibility', 'published_at', 'created_by', 'is_featured', 'is_active']
    list_filter = ['church', 'visibility', 'is_featured', 'is_active', 'event_date']
    search_fields = ['title', 'description']
    prepopulated_fields = {'slug': ('title',)}


@admin.register(Sermon)
class SermonAdmin(admin.ModelAdmin):
    """Manage sermons from the Django admin."""

    list_display = ['title', 'church', 'slug', 'preacher', 'sermon_date', 'visibility', 'published_at', 'created_by', 'views_count']
    list_filter = ['church', 'visibility', 'is_featured', 'is_active']
    search_fields = ['title', 'preacher', 'bible_reference']
    prepopulated_fields = {'slug': ('title',)}


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    """Manage member records from the Django admin."""

    list_display = ['last_name', 'first_name', 'church', 'phone', 'department', 'directory_consent', 'directory_consent_at', 'is_active']
    list_filter = ['church', 'gender', 'department', 'directory_consent', 'is_active']
    search_fields = ['first_name', 'last_name', 'email', 'phone']


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    """Manage public pages from the Django admin."""

    list_display = ['title', 'church', 'slug', 'sort_order', 'is_in_menu', 'visibility', 'published_at', 'created_by', 'is_active']
    list_filter = ['church', 'is_in_menu', 'visibility', 'is_active']
    prepopulated_fields = {'slug': ('title',)}


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    """Review inbound contact messages from the Django admin."""

    list_display = ['sender_name', 'sender_email', 'subject', 'church', 'status', 'assigned_to', 'responded_at', 'created_at']
    list_filter = ['church', 'status', 'assigned_to']
    search_fields = ['sender_name', 'sender_email', 'subject', 'message']


@admin.register(ContactMessageReply)
class ContactMessageReplyAdmin(admin.ModelAdmin):
    """Inspect replies attached to contact messages."""

    list_display = ['message', 'created_by', 'created_at']
    list_filter = ['created_by', 'created_at']


@admin.register(ChurchMembership)
class ChurchMembershipAdmin(admin.ModelAdmin):
    """Manage tenant memberships from the Django admin."""

    list_display = ['user', 'church', 'role', 'is_active', 'created_at']
    list_filter = ['church', 'role', 'is_active']
    search_fields = ['user__username', 'user__email', 'church__name']


@admin.register(ChurchInvitation)
class ChurchInvitationAdmin(admin.ModelAdmin):
    """Track pending and historical invitations from the Django admin."""

    list_display = ['email', 'church', 'role', 'status', 'invited_by', 'created_at', 'expires_at']
    list_filter = ['church', 'role', 'status']
    search_fields = ['email', 'church__name', 'invited_by__username']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Inspect user notifications from the Django admin."""

    list_display = ['title', 'recipient', 'church', 'category', 'is_read', 'created_at']
    list_filter = ['church', 'category', 'is_read']
    search_fields = ['title', 'body', 'recipient__username']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Review audit history from the Django admin."""

    list_display = ['action', 'object_type', 'object_id', 'church', 'actor', 'created_at']
    list_filter = ['action', 'object_type', 'church']
    search_fields = ['object_type', 'object_id', 'object_repr', 'actor__username']


@admin.register(BackgroundJob)
class BackgroundJobAdmin(admin.ModelAdmin):
    """Inspect durable background jobs from the Django admin."""

    list_display = ['job_type', 'status', 'attempts', 'available_at', 'created_at', 'completed_at']
    list_filter = ['job_type', 'status']
    search_fields = ['job_type', 'last_error']


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    """Manage global platform settings from the Django admin."""

    list_display = ['site_name', 'contact_email']
