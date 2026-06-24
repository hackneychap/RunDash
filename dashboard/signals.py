"""Signal handlers for dashboard models."""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache

from .models import RunActivity, TrainingBlock


def link_runs_to_block(block, dry_run=False):
    """
    Link any RunActivity whose date falls within block.start_date..end_date
    to this block. If multiple blocks overlap a given run, the one with the
    latest end_date wins (most recent A race).

    Returns (linked_count, unlinked_count).
    """
    candidate_runs = RunActivity.objects.filter(
        date__gte=block.start_date,
        date__lte=block.end_date,
    )

    linked = 0
    unlinked = 0

    for run in candidate_runs:
        blocks = TrainingBlock.objects.filter(
            start_date__lte=run.date,
            end_date__gte=run.date,
        ).order_by("-end_date")

        best_block = blocks.first()
        if best_block is None:
            continue

        if run.training_block_id != best_block.id:
            if not dry_run:
                run.training_block = best_block
                run.save(update_fields=["training_block"])
            linked += 1

    return linked, unlinked


@receiver(post_save, sender=TrainingBlock)
def training_block_saved(sender, instance, created, **kwargs):
    """When a TrainingBlock is created or its dates change, re-link runs."""
    link_runs_to_block(instance)


@receiver([post_save, post_delete], sender=RunActivity)
@receiver([post_save, post_delete], sender=TrainingBlock)
def invalidate_dashboard_cache(sender, instance, **kwargs):
    """Invalidate dashboard cache when runs or training blocks are added, updated, or deleted."""
    cache.delete('dashboard_context')
