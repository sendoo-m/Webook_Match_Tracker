from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

PLAN_APPROVAL_ALLOWED_EXTENSIONS = ["jpg", "jpeg", "png", "pdf", "doc", "docx", "xls", "xlsx"]
PLAN_APPROVAL_MAX_SIZE_MB = 10


def validate_plan_approval_file(value):
    """Keeps the SPL "plan approval" upload to images/office docs only, and
    under a sane size - the field otherwise has no other constraint on what
    gets attached."""
    extension = value.name.rsplit(".", 1)[-1].lower() if "." in value.name else ""
    if extension not in PLAN_APPROVAL_ALLOWED_EXTENSIONS:
        raise ValidationError(
            _("Unsupported file type. Allowed types: %(extensions)s.")
            % {"extensions": ", ".join(PLAN_APPROVAL_ALLOWED_EXTENSIONS)}
        )
    if value.size > PLAN_APPROVAL_MAX_SIZE_MB * 1024 * 1024:
        raise ValidationError(
            _("File is too large. Maximum size is %(max_mb)s MB.") % {"max_mb": PLAN_APPROVAL_MAX_SIZE_MB}
        )


class Competition(models.Model):
    name_ar = models.CharField(max_length=150, unique=True)
    name_en = models.CharField(max_length=150, unique=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name_ar"]

    def __str__(self):
        return self.name_ar or self.name_en


class UserCompetitionAccess(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="competition_access",
        on_delete=models.CASCADE,
    )
    competition = models.ForeignKey(
        Competition,
        related_name="user_access",
        on_delete=models.CASCADE,
    )
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "competition")
        ordering = ("competition__sort_order", "user__username")
        verbose_name = "User Competition Access"
        verbose_name_plural = "User Competition Access Grants"

    def __str__(self):
        return f"{self.user} → {self.competition}"


class Club(models.Model):
    name_ar = models.CharField(max_length=150, unique=True)
    name_en = models.CharField(max_length=150, unique=True)
    short_name = models.CharField(max_length=50, blank=True)
    logo = models.ImageField(upload_to="club_logos/", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_test_club = models.BooleanField(
        default=False,
        help_text="Excluded from every user-facing club list/filter/report - for dummy fixtures used in testing, not real teams.",
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_clubs",
        null=True,
        blank=True,
        help_text="الموظف المسؤول عن مباريات هذا النادي.",
    )

    class Meta:
        ordering = ["name_ar"]

    def __str__(self):
        return self.name_ar or self.name_en


class Venue(models.Model):
    name_ar = models.CharField(max_length=255)
    name_en = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120, blank=True)
    google_maps_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name_ar"]

    def __str__(self):
        return self.name_ar or self.name_en


class Match(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        IN_PROGRESS = "in_progress", "In Progress"
        READY_FOR_CMS = "ready_for_cms", "Ready for CMS"
        SENT_TO_CMS = "sent_to_cms", "Sent to CMS"
        PUBLISHED = "published", "Published"

    class ReleaseDelayReason(models.TextChoices):
        SPL_SCHEDULE_MISSING = "spl_schedule_missing", "SPL hasn't provided the match schedule/dates yet"
        KVS_DELAY = "kvs_delay", "KVs delay"
        OTHER = "other", "Other"

    competition = models.ForeignKey(
        Competition,
        related_name="matches",
        on_delete=models.PROTECT,
    )
    home_club = models.ForeignKey(
        Club,
        related_name="home_matches",
        on_delete=models.PROTECT,
    )
    away_club = models.ForeignKey(
        Club,
        related_name="away_matches",
        on_delete=models.PROTECT,
    )
    venue = models.ForeignKey(
        Venue,
        related_name="matches",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )

    round_number = models.PositiveIntegerField(null=True, blank=True)
    slug = models.SlugField(max_length=255, unique=True)

    title_ar = models.CharField(max_length=255)
    title_en = models.CharField(max_length=255)
    description_ar = models.TextField(blank=True)
    description_en = models.TextField(blank=True)

    sale_starts_at = models.DateTimeField(null=True, blank=True)
    event_date = models.DateField(null=True, blank=True)
    gates_open_time = models.TimeField(null=True, blank=True)
    match_start_time = models.TimeField(null=True, blank=True)
    match_end_time = models.TimeField(null=True, blank=True)

    discount_code = models.CharField(max_length=50, blank=True)
    discount_percentage = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
    )
    discount_ticket_count = models.PositiveIntegerField(null=True, blank=True)

    # SPL report fields. Round, date, teams, stadium, and release date reuse
    # the fields above (round_number, event_date, home_club/away_club, venue,
    # sale_starts_at) - only the SPL-specific extras live here. KV/Webook
    # Images and Webook Readiness are NOT stored: they're derived from the
    # match checklist (see operations/views/helpers.py build_spl_report_row).
    actual_release_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When tickets actually went live, if different from the planned sale_starts_at.",
    )
    webook_purchase_url = models.URLField(
        blank=True,
        help_text="Public ticket purchase link on webook.com, filled in once the match goes live/published.",
    )
    ticketing_plan_approved = models.BooleanField(default=False)
    ticketing_plan_approved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the SPL team confirmed the ticketing plan - kept even after the match is finished, for the Finished Matches history.",
    )
    spl_tickets_sent = models.BooleanField(default=False)
    spl_tickets_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the SPL team confirmed complimentary tickets were sent.",
    )
    spl_comments = models.TextField(blank=True)
    plan_approval_file = models.FileField(
        upload_to="spl_plan_approvals/",
        null=True,
        blank=True,
        validators=[validate_plan_approval_file],
        help_text="Signed ticketing plan approval document (image, PDF, or Office file).",
    )
    plan_approval_file_uploaded_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the current plan_approval_file was uploaded.",
    )

    # Explains WHY ticket sale release is running late, per the Match
    # Release Schedule page - purely descriptive, doesn't affect any other
    # computed status (release lateness itself is derived from event_date
    # and actual_release_at, not stored - see operations/views/helpers.py
    # compute_release_status).
    release_delay_reason = models.CharField(
        max_length=30,
        choices=ReleaseDelayReason.choices,
        blank=True,
    )
    release_delay_notes = models.TextField(
        blank=True,
        help_text="Details for the delay reason - e.g. which club/party the ticket design delay is on.",
    )

    # Added for the Google Calendar import (matches/calendar_sync.py): the
    # calendar feed has no equivalent of these, so the importer always
    # stamps the same constant text/False - they exist mainly so the
    # calendar import's Excel export has somewhere to read Terms/Images from.
    terms_ar = models.TextField(blank=True, default="لا يوجد استرجاع للمبالغ.")
    terms_en = models.TextField(blank=True, default="Refund is not allowed.")
    has_images = models.BooleanField(
        default=False,
        help_text=(
            "Manually confirmed marketing images are ready. NOT the same as "
            "the KV/Webook Images readiness on the SPL Report, which is "
            "derived from checklist items - this field is only ever set by "
            "hand or left False by the calendar import."
        ),
    )

    cms_status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    sent_to_cms_at = models.DateTimeField(null=True, blank=True)
    sent_to_cms_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cms_sent_matches",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["event_date", "match_start_time", "id"]

    def __str__(self):
        return self.title_en

    @property
    def has_discount(self):
        return bool(self.discount_code)

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