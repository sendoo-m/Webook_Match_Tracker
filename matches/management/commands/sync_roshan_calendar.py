# matches/management/commands/sync_roshan_calendar.py
#
# `python manage.py sync_roshan_calendar` - runs the same Google Calendar
# sync as the "Update Roshan League Schedule" button in Django Admin and the
# Control Panel's Matches page (matches.calendar_sync.sync_roshan_league_from_calendar),
# but from the command line so it can be put on a schedule (Windows Task
# Scheduler, cron, etc.) to keep the fixture list continuously up to date
# without anyone clicking a button.
#
# Example Windows Task Scheduler action, run every 30 minutes:
#   Program: D:\2025\webook-match-tracker\venv\Scripts\python.exe
#   Arguments: manage.py sync_roshan_calendar
#   Start in: D:\2025\webook-match-tracker\config

from django.core.management.base import BaseCommand, CommandError

from matches.calendar_sync import CalendarSyncError, sync_roshan_league_from_calendar


class Command(BaseCommand):
    help = "Syncs Roshan League fixtures from SPL's Google Calendar feed into the database (all rounds, every run)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--min-round", type=int, default=None, help="Only sync rounds >= this number (default: no minimum)."
        )
        parser.add_argument(
            "--max-round", type=int, default=None, help="Only sync rounds <= this number (default: no maximum)."
        )

    def handle(self, *args, **options):
        try:
            result = sync_roshan_league_from_calendar(
                min_round=options["min_round"],
                max_round=options["max_round"],
            )
        except CalendarSyncError as exc:
            raise CommandError(str(exc))

        self.stdout.write(
            self.style.SUCCESS(
                f"Calendar sync completed. Created: {result.created}, updated: {result.updated}, "
                f"ignored (unparsed round or out of --min-round/--max-round): {result.ignored_out_of_range}."
            )
        )
        for summary, reason in result.skipped:
            self._write_safely(f"Skipped: {summary} - {reason}")

    def _write_safely(self, text):
        # Scheduled runs (Windows Task Scheduler, cron redirected to a log
        # file) often land on a console/file encoding that can't render
        # Arabic or emoji from the calendar's own text - fall back to an
        # ASCII-safe version instead of crashing the whole command over one
        # unprintable skip message.
        try:
            self.stdout.write(self.style.WARNING(text))
        except UnicodeEncodeError:
            self.stdout.write(self.style.WARNING(text.encode("ascii", "backslashreplace").decode("ascii")))
