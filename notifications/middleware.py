# notifications/middleware.py

from django.utils import timezone


class DailyNotificationSweepMiddleware:
    """Safety net for the 25-day/20-day/match-live notification sweep: runs
    notifications.services.run_daily_notification_sweep at most once per
    calendar day (Riyadh-local), gated by SiteSettings.notifications_last_run_date,
    in case the Windows Task Scheduler job documented in
    generate_daily_notifications.py's docstring is never configured or
    silently stops running. Only does real work on the first authenticated
    request of a new day - every other request pays one cheap date
    comparison (SiteSettings.load() is already queried every request by
    control_panel.context_processors.panel_nav_flag, so this reuses that
    same singleton row rather than adding a second query)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(request.user, "is_authenticated", False):
            self._maybe_run_sweep()
        return self.get_response(request)

    def _maybe_run_sweep(self):
        from control_panel.models import SiteSettings

        today = timezone.localdate()
        settings_obj = SiteSettings.load()
        if settings_obj.notifications_last_run_date == today:
            return

        from .services import run_daily_notification_sweep

        run_daily_notification_sweep()
        settings_obj.notifications_last_run_date = today
        settings_obj.save(update_fields=["notifications_last_run_date"])
