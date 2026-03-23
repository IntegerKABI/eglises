"""Process queued background jobs for the church platform."""

import time

from django.core.management.base import BaseCommand

from church.background_jobs import DEFAULT_JOB_LIMIT, process_pending_background_jobs


class Command(BaseCommand):
    """Run queued background jobs once or in a long-running worker loop."""

    help = "Process queued background jobs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=DEFAULT_JOB_LIMIT,
            help="Maximum number of jobs to process per iteration.",
        )
        parser.add_argument(
            "--loop",
            action="store_true",
            help="Keep polling for jobs instead of exiting after one iteration.",
        )
        parser.add_argument(
            "--sleep",
            type=int,
            default=5,
            help="Seconds to sleep between loop iterations when no jobs are available.",
        )

    def handle(self, *args, **options):
        limit = max(1, options["limit"])
        sleep_seconds = max(1, options["sleep"])
        run_forever = options["loop"]

        while True:
            processed = process_pending_background_jobs(limit=limit)
            self.stdout.write(f"Processed {processed} background job(s).")
            if not run_forever:
                return
            if processed == 0:
                time.sleep(sleep_seconds)
