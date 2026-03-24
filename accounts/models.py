"""Custom account models for the church platform."""

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Extend the default Django user with church-specific profile data."""

    phone = models.CharField(max_length=30, blank=True, verbose_name="Téléphone")

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"

    def __str__(self):
        return self.get_username()
