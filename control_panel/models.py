from datetime import date

from django.db import models


class SiteSettings(models.Model):
    """Site-wide branding/config - deliberately a singleton (always pk=1),
    the first one in this codebase. Loaded via SiteSettings.load() rather
    than a plain queryset lookup so every call site gets a real instance
    (with defaults) even before anyone has ever saved one, instead of
    having to guard against DoesNotExist everywhere it's used."""

    site_name_ar = models.CharField(max_length=150, blank=True)
    site_name_en = models.CharField(max_length=150, blank=True)
    logo = models.ImageField(upload_to="site/", blank=True, null=True)

    # Phase 3 (daily notification generation) reads/writes this so the
    # request-time fallback trigger only does real work once per calendar
    # day, regardless of how many requests land that day.
    notifications_last_run_date = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "Site Settings"
        verbose_name_plural = "Site Settings"

    def __str__(self):
        return "Site Settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def load(cls):
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj


class ReleaseNote(models.Model):
    version = models.CharField(max_length=20, unique=True, help_text="e.g. 1.0.0")
    release_date = models.DateField(default=date.today)
    highlights = models.TextField(help_text="What's new in this version - one item per line.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-release_date", "-id"]
        verbose_name = "Release Note"

    def __str__(self):
        return f"v{self.version}"

    @property
    def highlight_lines(self):
        return [line.strip() for line in self.highlights.splitlines() if line.strip()]


class FeedbackEntry(models.Model):
    class Category(models.TextChoices):
        RECOMMENDATION = "recommendation", "Recommendations & Suggestions"
        SOFTWARE = "software", "Software Improvements"
        DESIGN = "design", "Design Improvements"
        INFRASTRUCTURE = "infrastructure", "Infrastructure Improvements"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending Review"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        IMPLEMENTED = "implemented", "Implemented"

    title = models.CharField(max_length=255)
    category = models.CharField(max_length=20, choices=Category.choices)
    submitted_by = models.CharField(max_length=150, help_text="Who suggested this.")
    situation_before = models.TextField(
        blank=True,
        help_text="The situation before this suggestion. Filled in by the reviewer.",
    )
    suggestion = models.TextField(help_text="What was suggested.")
    situation_after = models.TextField(
        blank=True,
        help_text="How things changed after implementation, if applicable.",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    decision_reason = models.TextField(blank=True, help_text="Why it was accepted, rejected, or implemented.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Feedback Entry"
        verbose_name_plural = "Feedback Entries"

    def __str__(self):
        return self.title
