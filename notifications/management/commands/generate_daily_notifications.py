# notifications/management/commands/generate_daily_notifications.py
#
# `python manage.py generate_daily_notifications` - walks every match and
# fires the 25-day club notice, the 20-day-not-live coordinator notice, and
# the match-live notice (see notifications.services.run_daily_notification_sweep
# for the actual logic - this command is a thin wrapper around it, matching
# matches/management/commands/sync_roshan_calendar.py's own pattern of "one
# function, callable from both the command line and a button/fallback").
#
# There is also a request-time fallback (operations/middleware.py) that runs
# this same sweep at most once per calendar day if the scheduled task below
# is ever missed, so notifications don't silently stop - but that fallback
# only fires on the first request of a new day, so it should not be relied
# on as the primary mechanism.
#
# Example Windows Task Scheduler action, run once daily (e.g. at 06:00):
#   Program: D:\2025\webook-match-tracker\venv\Scripts\python.exe
#   Arguments: manage.py generate_daily_notifications
#   Start in: D:\2025\webook-match-tracker\config

from django.core.management.base import BaseCommand

from notifications.services import run_daily_notification_sweep


class Command(BaseCommand):
    help = "Generates the daily match-based notifications (25-day club notice, 20-day coordinator notice, match-live notice)."

    def handle(self, *args, **options):
        counts = run_daily_notification_sweep()
        self._write_safely(
            "Daily notification sweep complete. "
            f"25-day: {counts.get('match_25_days', 0)}, "
            f"20-day-not-live: {counts.get('match_20_days_not_live', 0)}, "
            f"match-live: {counts.get('match_live', 0)}."
        )

    def _write_safely(self, text):
        # Same reasoning as sync_roshan_calendar.py: a scheduled run's
        # console/log encoding may not render every character cleanly.
        try:
            self.stdout.write(self.style.SUCCESS(text))
        except UnicodeEncodeError:
            self.stdout.write(self.style.SUCCESS(text.encode("ascii", "backslashreplace").decode("ascii")))
