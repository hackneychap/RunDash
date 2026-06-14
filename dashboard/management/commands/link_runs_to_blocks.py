"""
Link RunActivity records to TrainingBlocks based on date overlap.

Idempotent: running multiple times is safe. Calls into the same
`link_runs_to_block` helper used by the post_save signal, so the
behaviour is identical.

Useful for:
- One-off backfills (e.g. after data imports before the signal was added)
- Recovery from manual DB edits
- Verifying the linking state without creating/saving a block
"""

from django.core.management.base import BaseCommand

from dashboard.models import TrainingBlock
from dashboard.signals import link_runs_to_block


class Command(BaseCommand):
    help = "Link RunActivity records to TrainingBlocks by date overlap."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be changed without writing to the database.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        total_linked = 0
        for block in TrainingBlock.objects.all().order_by("start_date"):
            linked, _unlinked = link_runs_to_block(block, dry_run=dry_run)
            total_linked += linked

        action = "Would link" if dry_run else "Linked"
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(f"Done. {action} {total_linked} run(s) across all blocks.")
        )