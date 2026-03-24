"""Admin configuration for account models."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Expose the custom user model in Django admin."""

    list_display = DjangoUserAdmin.list_display + ("phone",)
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Informations supplémentaires", {"fields": ("phone",)}),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ("Informations supplémentaires", {"fields": ("phone",)}),
    )
