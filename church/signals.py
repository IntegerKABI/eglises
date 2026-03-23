from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Church, Event, Sermon, Page
from .cache import bump_church_cache_version

@receiver([post_save, post_delete], sender=Church)
def invalidate_church_cache(sender, instance, **kwargs):
    bump_church_cache_version(None)
    if hasattr(instance, 'slug'):
        bump_church_cache_version(instance.slug)

@receiver([post_save, post_delete], sender=Event)
@receiver([post_save, post_delete], sender=Sermon)
@receiver([post_save, post_delete], sender=Page)
def invalidate_church_content_cache(sender, instance, **kwargs):
    if instance.church:
        bump_church_cache_version(instance.church.slug)
