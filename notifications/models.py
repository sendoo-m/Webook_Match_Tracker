from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Notification(models.Model):
    """An in-app notification for one recipient. Created explicitly by
    notifications/services.py right after the triggering event (matching
    operations.views.helpers.log_match_activity's convention of an explicit
    call after the mutating .save(), rather than a signal). `message` is
    rendered once at creation time, not re-derived at display time, so a
    notification's wording stays a stable record of what happened even if
    the underlying match/plan changes afterward."""

    class NotificationType(models.TextChoices):
        PRICING_PLAN_UPLOADED = "pricing_plan_uploaded", _("Pricing plan uploaded")
        MATCH_25_DAYS = "match_25_days", _("25 days to match")
        MATCH_20_DAYS_NOT_LIVE = "match_20_days_not_live", _("20 days to match, not live")
        MATCH_LIVE = "match_live", _("Match went live")

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    notification_type = models.CharField(max_length=30, choices=NotificationType.choices)
    match = models.ForeignKey(
        "matches.Match",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    plan = models.ForeignKey(
        "operations.ClubPricingPlan",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.message

    @property
    def is_read(self):
        return self.read_at is not None
