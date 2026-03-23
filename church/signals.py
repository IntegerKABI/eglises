from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Church, ChurchInvitation, ChurchMembership, Event, Member, Page, Sermon
from .cache import bump_church_cache_version
from .limits import invalidate_plan_usage_cache

@receiver([post_save, post_delete], sender=Church)
def invalidate_church_cache(sender, instance, **kwargs):
    bump_church_cache_version(None)
    if hasattr(instance, 'slug'):
        bump_church_cache_version(instance.slug)
    invalidate_plan_usage_cache(instance.pk)

@receiver([post_save, post_delete], sender=Event)
@receiver([post_save, post_delete], sender=Sermon)
@receiver([post_save, post_delete], sender=Page)
@receiver([post_save, post_delete], sender=Member)
@receiver([post_save, post_delete], sender=ChurchMembership)
@receiver([post_save, post_delete], sender=ChurchInvitation)
def invalidate_church_content_cache(sender, instance, **kwargs):
    if instance.church:
        bump_church_cache_version(instance.church.slug)
        invalidate_plan_usage_cache(instance.church_id)
