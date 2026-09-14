from django.conf import settings
from django.db import models

from matches.models import Club, Match, validate_plan_approval_file


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


class ClubPricingPlan(models.Model):
    """The home club's own pricing-plan document for one of its matches -
    entirely separate from Match.plan_approval_file/ticketing_plan_approved
    (SPL's side of ticketing approval) and from cms_status/spl_tickets_sent.
    Those fields keep their existing meaning untouched; this model exists
    so "the club uploaded a plan", "SPL approved a plan", and "the match
    went live" can never be collapsed into one flag by accident.

    Append-only versioning: every upload creates a new row with the next
    version number for that match rather than overwriting the previous
    one, so nothing is silently replaced - see
    operations/views/club_dashboard.py's upload view for how `version` is
    computed. The current plan for a match is simply the highest version
    row (Meta.ordering already puts it first).
    """

    class Status(models.TextChoices):
        # A strictly linear, one-way lifecycle for THIS specific plan
        # version - no branching, no SPL decision states (approved/
        # rejected/needs-changes) here on purpose: that's SPL's own call,
        # tracked entirely by the existing Match.ticketing_plan_approved,
        # never by this field. This model only ever tracks what the CLUB
        # did: uploaded it, sent it, confirmed the send.
        UPLOADED = "uploaded", "Uploaded"
        SUBMITTED_TO_SPL = "submitted_to_spl", "Submitted to SPL"
        SUBMISSION_CONFIRMED = "submission_confirmed", "Submission Confirmed"

    match = models.ForeignKey(
        Match,
        related_name="club_pricing_plans",
        on_delete=models.CASCADE,
    )
    # Always the match's home club - set server-side from match.home_club
    # at creation (see the upload view), never from request data. Kept as
    # its own column (rather than always joining through match.home_club)
    # so a plan's ownership survives even if a match's home_club were ever
    # reassigned, and so "all of this club's plans" is a direct filter.
    club = models.ForeignKey(
        Club,
        related_name="pricing_plans",
        on_delete=models.PROTECT,
    )
    # Nullable - a plan submitted via structured per-category prices (see
    # ClubPricingPlanCategoryPrice) may have no attached document at all.
    # Still supported/optional for a club that just wants to attach a file
    # instead of/alongside entering prices per category.
    file = models.FileField(
        upload_to="club_pricing_plans/",
        validators=[validate_plan_approval_file],
        null=True,
        blank=True,
        help_text="Pricing plan document uploaded by the home club (same allowed types/size as the SPL plan approval file). Optional if category prices were entered instead.",
    )
    version = models.PositiveIntegerField(
        help_text="1 for a match's first upload, incrementing per match - never reused or edited after creation.",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.UPLOADED,
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="uploaded_pricing_plans",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    # "Club submitted" - deliberately its own pair of fields, never
    # confused with Match.sent_to_cms_at/sent_to_cms_by (the CMS
    # submission, a different action entirely) or with SPL's own
    # ticketing_plan_approved/ticketing_plan_approved_at.
    submitted_at = models.DateTimeField(null=True, blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="submitted_pricing_plans",
    )

    # "Club confirmed the submission" - a separate club-side acknowledgement
    # that the send happened, still not an SPL decision of any kind.
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="confirmed_pricing_plans",
    )

    class SPLDecision(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    # SPL's own decision on THIS plan version - orthogonal to the club-side
    # status above and to Match.ticketing_plan_approved. Approving here also
    # sets ticketing_plan_approved=True on the match (kept in sync so every
    # existing boolean-consuming page - SPL Report, Finished Matches,
    # Missing Requirements, match_spl_info_box - keeps working unchanged);
    # rejecting sets it back to False, which is what re-opens
    # can_upload_home_match_pricing_plan for a corrected re-submission.
    spl_decision = models.CharField(max_length=10, choices=SPLDecision.choices, default=SPLDecision.PENDING)
    spl_decision_at = models.DateTimeField(null=True, blank=True)
    spl_decision_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="decided_pricing_plans",
    )
    spl_decision_note = models.TextField(
        blank=True,
        help_text="Required when rejecting - explains what needs to change.",
    )

    # A frozen PNG (seat-map image + a price badge per positioned category,
    # baked into the pixels) generated at the moment SPL decides on this
    # plan - see generate_seat_map_snapshot(). Deliberately NOT the same
    # thing as the live seat_map_groups() render: block positions or the
    # venue image itself can be edited later in the Control Panel, and this
    # snapshot must keep showing exactly what SPL saw when they decided,
    # regardless of any such later edit.
    seat_map_snapshot = models.ImageField(upload_to="club_pricing_plan_snapshots/", null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-version",)
        constraints = [
            models.UniqueConstraint(fields=["match", "version"], name="unique_club_pricing_plan_version_per_match"),
        ]
        verbose_name = "Club Pricing Plan"
        verbose_name_plural = "Club Pricing Plans"

    def __str__(self):
        return f"{self.match} - v{self.version} ({self.club})"

    def seat_map_groups(self):
        """Splits this plan's category prices into {"image": VenueImage,
        "prices": [...]} groups (one per seating-map image a block was
        positioned on - normally just one) plus a leftover "unplaced" list
        for any category price whose block has no on-image position yet, so
        the seat-map display degrades to a plain price table instead of
        silently dropping those categories."""
        prices = self.category_prices.select_related("category", "category__position_image").all()
        images_by_id = {}
        unplaced = []
        for category_price in prices:
            category = category_price.category
            if category.has_position:
                image_id = category.position_image_id
                if image_id not in images_by_id:
                    images_by_id[image_id] = {"image": category.position_image, "prices": []}
                images_by_id[image_id]["prices"].append(category_price)
            else:
                unplaced.append(category_price)
        return {"images": list(images_by_id.values()), "unplaced": unplaced}

    def generate_seat_map_snapshot(self):
        """Renders seat_map_groups()'s positioned categories onto a real PNG
        (one badge per block, baked into the pixels at its saved x/y%) and
        saves it to seat_map_snapshot - called once, at the moment SPL
        approves or rejects this plan (see spl/views/pricing_plan_decision.py).
        A no-op if no category on this plan has a saved position yet."""
        from io import BytesIO

        from django.core.files.base import ContentFile
        from PIL import Image, ImageDraw, ImageFont

        groups = self.seat_map_groups()["images"]
        if not groups:
            return

        # Only one image group is the common case (every category placed on
        # the same venue photo) - a plan spanning more than one would need
        # more than a single flat PNG to represent, so the first group is
        # used as this snapshot's base, matching what the page shows first.
        group = groups[0]
        with group["image"].image.open("rb") as source_file:
            base_image = Image.open(source_file).convert("RGB")
            base_image.load()

        draw = ImageDraw.Draw(base_image)
        try:
            font = ImageFont.load_default(size=max(14, base_image.width // 80))
        except TypeError:
            # Older Pillow: load_default() takes no size argument.
            font = ImageFont.load_default()

        for category_price in group["prices"]:
            category = category_price.category
            label = f"{category.code}: {category_price.price}"
            x = category.position_x / 100 * base_image.width
            y = category.position_y / 100 * base_image.height

            bbox = draw.textbbox((0, 0), label, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            padding = 6
            box = (
                x - text_width / 2 - padding, y - text_height / 2 - padding,
                x + text_width / 2 + padding, y + text_height / 2 + padding,
            )
            draw.rounded_rectangle(box, radius=6, fill=(255, 255, 255), outline=(60, 60, 60), width=1)
            draw.text((x, y), label, font=font, fill=(20, 20, 20), anchor="mm")

        buffer = BytesIO()
        base_image.save(buffer, format="PNG")
        self.seat_map_snapshot.save(
            f"plan-{self.pk}-seat-map.png", ContentFile(buffer.getvalue()), save=False
        )
        self.save(update_fields=["seat_map_snapshot"])


class ClubPricingPlanCategoryPrice(models.Model):
    """One category's price for a specific ClubPricingPlan version - the
    structured alternative (or complement) to just attaching a raw file.
    Prices against VenueSeatingCategory codes, which are scoped to
    (venue, club) and managed in the Control Panel; PROTECT on delete so
    a coordinator can't remove a category out from under a plan that
    already priced against it."""

    plan = models.ForeignKey(
        ClubPricingPlan,
        related_name="category_prices",
        on_delete=models.CASCADE,
    )
    category = models.ForeignKey(
        "matches.VenueSeatingCategory",
        related_name="pricing_plan_prices",
        on_delete=models.PROTECT,
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["plan", "category"], name="unique_category_price_per_plan"),
        ]
        ordering = ("category__sort_order", "category__code")
        verbose_name = "Club Pricing Plan Category Price"
        verbose_name_plural = "Club Pricing Plan Category Prices"

    def __str__(self):
        return f"{self.plan} - {self.category.code}: {self.price}"