from django.conf import settings
from django.db import models
from django.utils import timezone

from matches.models import Match


class ChecklistCategory(models.Model):
    name = models.CharField(max_length=120, unique=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "id")
        verbose_name = "Checklist Category"
        verbose_name_plural = "Checklist Categories"

    def __str__(self):
        return self.name


class ChecklistTemplateItem(models.Model):
    category = models.ForeignKey(
        ChecklistCategory,
        related_name="template_items",
        on_delete=models.PROTECT,
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_required = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("category__sort_order", "sort_order", "id")
        verbose_name = "Checklist Template Item"
        verbose_name_plural = "Checklist Template Items"

    def __str__(self):
        return self.title


class MatchChecklistItem(models.Model):
    class Status(models.TextChoices):
        NOT_STARTED = "not_started", "Not Started"
        IN_PROGRESS = "in_progress", "In Progress"
        DONE = "done", "Done"
        DELAYED = "delayed", "Delayed"

    match = models.ForeignKey(
        Match,
        related_name="checklist_items",
        on_delete=models.CASCADE,
    )
    template_item = models.ForeignKey(
        ChecklistTemplateItem,
        related_name="match_items",
        on_delete=models.PROTECT,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NOT_STARTED,
    )
    note = models.TextField(blank=True)
    delay_reason = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="completed_match_checklist_items",
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = (
            "match_id",
            "template_item__category__sort_order",
            "template_item__sort_order",
            "id",
        )
        unique_together = ("match", "template_item")
        verbose_name = "Match Checklist Item"
        verbose_name_plural = "Match Checklist Items"

    def __str__(self):
        return f"{self.match} - {self.template_item}"

    def save(self, *args, **kwargs):
        if self.status == self.Status.DONE:
            if self.completed_at is None:
                self.completed_at = timezone.now()
        else:
            self.completed_at = None

        super().save(*args, **kwargs)

        if self.match_id:
            self.match.refresh_checklist_status()


class CMSSubmission(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        CONFIRMED = "confirmed", "Confirmed"

    match = models.OneToOneField(
        Match,
        related_name="cms_submission",
        on_delete=models.CASCADE,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cms_submissions_sent",
    )
    cms_reference = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "CMS Submission"
        verbose_name_plural = "CMS Submissions"

    def __str__(self):
        return f"CMS Submission - {self.match}"