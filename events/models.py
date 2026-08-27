from django.conf import settings
from django.db import models
from django.utils import timezone

from matches.models import Venue


class CategoryGroup(models.Model):
    """The 4 fixed top-level buckets shown on Webook's platform Events tab:
    Events, Seasons, Experiences, Dining. Not meant to be added-to via the
    UI - seeded once by events/management/commands/seed_event_categories.py."""

    class Code(models.TextChoices):
        EVENTS = "events", "Events"
        SEASONS = "seasons", "Seasons"
        EXPERIENCES = "experiences", "Experiences"
        DINING = "dining", "Dining"

    code = models.CharField(max_length=20, choices=Code.choices, unique=True)
    name_ar = models.CharField(max_length=120)
    name_en = models.CharField(max_length=120)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "Category Group"
        verbose_name_plural = "Category Groups"

    def __str__(self):
        return self.name_en


class Category(models.Model):
    """A specific category under a group, e.g. "Concerts & Music" under
    Events, or "Riyadh Season" under Seasons. Names can repeat across
    groups (e.g. "Sports" appears under both Events and Experiences)."""

    group = models.ForeignKey(CategoryGroup, related_name="categories", on_delete=models.PROTECT)
    name_ar = models.CharField(max_length=150)
    name_en = models.CharField(max_length=150)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["group__sort_order", "sort_order", "id"]
        unique_together = ("group", "name_en")
        verbose_name = "Category"
        verbose_name_plural = "Categories"

    def __str__(self):
        return f"{self.name_en} ({self.group.name_en})"


class Event(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        IN_PROGRESS = "in_progress", "In Progress"
        READY_FOR_CMS = "ready_for_cms", "Ready for CMS"
        SENT_TO_CMS = "sent_to_cms", "Sent to CMS"
        PUBLISHED = "published", "Published"

    category = models.ForeignKey(Category, related_name="events", on_delete=models.PROTECT)
    venue = models.ForeignKey(
        Venue,
        related_name="events",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )

    slug = models.SlugField(max_length=255, unique=True)
    title_ar = models.CharField(max_length=255)
    title_en = models.CharField(max_length=255)
    description_ar = models.TextField(blank=True)
    description_en = models.TextField(blank=True)

    event_date = models.DateField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    gates_open_time = models.TimeField(null=True, blank=True)
    sale_starts_at = models.DateTimeField(null=True, blank=True)
    actual_release_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When tickets actually went live, if different from the planned sale_starts_at.",
    )

    cms_status = models.CharField(max_length=30, choices=Status.choices, default=Status.DRAFT)
    sent_to_cms_at = models.DateTimeField(null=True, blank=True)
    sent_to_cms_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="events_sent_to_cms",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["event_date", "start_time", "id"]

    def __str__(self):
        return self.title_en

    def refresh_checklist_status(self):
        active_items = self.checklist_items.filter(is_active=True)
        required_items = active_items.filter(template_item__is_required=True)

        total_active = active_items.count()
        done_active = active_items.filter(status="done").count()
        delayed_active = active_items.filter(status="delayed").count()

        required_total = required_items.count()
        required_done = required_items.filter(status="done").count()
        required_delayed = required_items.filter(status="delayed").count()

        if self.cms_status in {self.Status.SENT_TO_CMS, self.Status.PUBLISHED}:
            return self

        if total_active == 0:
            new_status = self.Status.DRAFT
        elif required_total > 0 and required_done == required_total and required_delayed == 0:
            new_status = self.Status.READY_FOR_CMS
        elif delayed_active > 0:
            new_status = self.Status.IN_PROGRESS
        elif done_active > 0:
            new_status = self.Status.IN_PROGRESS
        else:
            new_status = self.Status.DRAFT

        if self.cms_status != new_status:
            self.cms_status = new_status
            self.save(update_fields=["cms_status", "updated_at"])

        return self


class EventChecklistCategory(models.Model):
    name = models.CharField(max_length=120, unique=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "id")
        verbose_name = "Event Checklist Category"
        verbose_name_plural = "Event Checklist Categories"

    def __str__(self):
        return self.name


class EventChecklistTemplateItem(models.Model):
    category = models.ForeignKey(
        EventChecklistCategory,
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
        verbose_name = "Event Checklist Template Item"
        verbose_name_plural = "Event Checklist Template Items"

    def __str__(self):
        return self.title


class EventChecklistItem(models.Model):
    class Status(models.TextChoices):
        NOT_STARTED = "not_started", "Not Started"
        IN_PROGRESS = "in_progress", "In Progress"
        DONE = "done", "Done"
        DELAYED = "delayed", "Delayed"

    event = models.ForeignKey(Event, related_name="checklist_items", on_delete=models.CASCADE)
    template_item = models.ForeignKey(
        EventChecklistTemplateItem,
        related_name="event_items",
        on_delete=models.PROTECT,
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOT_STARTED)
    note = models.TextField(blank=True)
    delay_reason = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="completed_event_checklist_items",
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = (
            "event_id",
            "template_item__category__sort_order",
            "template_item__sort_order",
            "id",
        )
        unique_together = ("event", "template_item")
        verbose_name = "Event Checklist Item"
        verbose_name_plural = "Event Checklist Items"

    def __str__(self):
        return f"{self.event} - {self.template_item}"

    def save(self, *args, **kwargs):
        if self.status == self.Status.DONE:
            if self.completed_at is None:
                self.completed_at = timezone.now()
        else:
            self.completed_at = None

        super().save(*args, **kwargs)

        if self.event_id:
            self.event.refresh_checklist_status()


class EventActivityLog(models.Model):
    class Action(models.TextChoices):
        CHECKLIST_UPDATED = "checklist_updated", "Checklist Updated"
        STATUS_CHANGED = "status_changed", "Status Changed"
        SENT_TO_CMS = "sent_to_cms", "Sent to CMS"

    event = models.ForeignKey(Event, related_name="activity_log", on_delete=models.CASCADE)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="event_activity_log_entries",
    )
    action = models.CharField(max_length=30, choices=Action.choices)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Event Activity Log"
        verbose_name_plural = "Event Activity Log"

    def __str__(self):
        return f"{self.event} - {self.get_action_display()}"


class EventCategoryAccess(models.Model):
    """Category-scoped role grant - the new permission mechanism for the
    events app: a user is a Coordinator or Admin for one or more Categories,
    mirroring how a Club Manager is scoped to clubs+competitions in the
    football app, but at the category level instead."""

    class Role(models.TextChoices):
        COORDINATOR = "coordinator", "Coordinator"
        ADMIN = "admin", "Admin"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="event_category_access",
        on_delete=models.CASCADE,
    )
    category = models.ForeignKey(Category, related_name="user_access", on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.COORDINATOR)
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "category")
        verbose_name = "Event Category Access"
        verbose_name_plural = "Event Category Access"

    def __str__(self):
        return f"{self.user} - {self.category} ({self.get_role_display()})"
