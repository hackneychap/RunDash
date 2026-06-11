from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import RunActivity

@receiver(post_save, sender=RunActivity)
@receiver(post_delete, sender=RunActivity)
def invalidate_dashboard_cache(sender, instance, **kwargs):
    # ⚡ Bolt Optimization: Cache invalidation
    # Clear the dashboard_context cache when RunActivity models are updated or deleted
    cache.delete('dashboard_context')
