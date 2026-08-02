from django.conf import settings
from django.db import models

from matches.models import Match


class MatchActivityLog(models.Model):
    class Action(models.TextChoices):
        CHECKLIST_UPDATED = "checklist_updated", "Checklist Updated"
        STATUS_CHANGED = "status_changed", "Status Changed"
        SENT_TO_CMS = "sent_to_cms", "Sent to CMS"

    match = models.ForeignKey(
        Match,
        related_name="activity_logs",
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="match_activity_logs",
    )
    action = models.CharField(
        max_length=50,
        choices=Action.choices,
    )
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        verbose_name = "Match Activity Log"
        verbose_name_plural = "Match Activity Logs"

    def __str__(self):
        return f"{self.match} - {self.get_action_display()}"