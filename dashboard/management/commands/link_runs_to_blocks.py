"""
Link RunActivity records to TrainingBlocks based on date overlap.

For each run without a training_block, find a block whose date range
encompasses the run date. If multiple blocks overlap, the one with the
latest end_date wins (i.e. the most recent A race block).

Also cleans up orphaned FKs (block deleted but FK not null — should be
impossible with SET_NULL, but defensive).

Idempotent: running multiple times is safe.
"""

from django.core.management.base import BaseCommand
from django.db.models import Q

from dashboard.models import RunActivity, TrainingBlock


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
        verbosity = options["verbosity"]

        linked = 0
        unlinked = 0

        # --- Step 1: Clean orphaned FKs ---
        # RunActivity.training_block has SET_NULL, so this should be a no-op,
        # but we check defensively in case of manual DB edits.
        orphans = RunActivity.objects.filter(
            training_block__isnull=False,
            training_block=None,
        )
        orphan_count = orphans.count()
        if orphan_count:
            if dry_run:
                self.stdout.write(
                    f"[dry-run] Would clear {orphan_count} orphaned training_block FK(s)"
                )
            else:
                orphans.update(training_block=None)
                unlinked = orphan_count
                self.stdout.write(
                    self.style.SUCCESS(f"Cleared {orphan_count} orphaned FK(s)")
                )

        # --- Step 2: Link unlinked runs ---
        runs = RunActivity.objects.filter(training_block__isnull=True).order_by("date")

        if not runs.exists():
            self.stdout.write("No unlinked runs found.")
        else:
            for run in runs:
                # Find all blocks whose date range covers this run.
                # latest end_date wins (most recent A race).
                blocks = TrainingBlock.objects.filter(
                    start_date__lte=run.date,
                    end_date__gte=run.date,
                ).order_by("-end_date")

                block = blocks.first()
                if block:
                    if dry_run:
                        self.stdout.write(
                            f"[dry-run] Would link run {run.activity_id} "
                            f"(date={run.date}) -> block '{block.name}' "
                            f"({block.start_date} to {block.end_date})"
                        )
                    else:
                        run.training_block = block
                        run.save(update_fields=["training_block"])
                    linked += 1

        # --- Summary ---
        action = "Would link" if dry_run else "Linked"
        action2 = "would clear" if dry_run else "cleared"

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {action} {linked} run(s), {action2} {unlinked} orphaned FK(s)."
            )
        )
