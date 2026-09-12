# operations/forms.py

from zoneinfo import ZoneInfo

from django import forms

from control_panel.models import FeedbackEntry
from matches.models import Match

RIYADH_TZ = ZoneInfo("Asia/Riyadh")


class MatchDiscountForm(forms.ModelForm):
    class Meta:
        model = Match
        fields = ["discount_code", "discount_percentage", "discount_ticket_count"]

    def clean(self):
        cleaned = super().clean()
        discount_code = cleaned.get("discount_code")
        discount_percentage = cleaned.get("discount_percentage")
        discount_ticket_count = cleaned.get("discount_ticket_count")

        if discount_code and (not discount_percentage or not discount_ticket_count):
            raise forms.ValidationError(
                "Discount percentage and number of tickets are required when a discount code is set."
            )
        if not discount_code and (discount_percentage or discount_ticket_count):
            raise forms.ValidationError(
                "A discount code is required when a discount percentage or ticket count is set."
            )
        return cleaned


class MatchSPLInfoForm(forms.ModelForm):
    class Meta:
        model = Match
        # actual_release_at defaults to being stamped automatically from the
        # CMS Status Control when a match is marked Published (see
        # operations/views/cms.py) - that stamp only fires once and never
        # overwrites an existing value. It's also editable here so it can be
        # corrected, or backfilled for matches that were published before
        # this field existed.
        fields = ["actual_release_at", "ticketing_plan_approved", "spl_tickets_sent", "spl_comments"]
        widgets = {
            "actual_release_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "spl_comments": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_actual_release_at(self):
        # Same convention as Match.sale_starts_at: the datetime-local widget
        # has no offset, so treat the entered wall-clock value as Asia/Riyadh.
        value = self.cleaned_data.get("actual_release_at")
        if value:
            return value.replace(tzinfo=RIYADH_TZ)
        return value


class SPLPlanApprovalUploadForm(forms.ModelForm):
    class Meta:
        model = Match
        fields = ["plan_approval_file"]


class WebookPurchaseLinkForm(forms.ModelForm):
    class Meta:
        model = Match
        fields = ["webook_purchase_url"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Postel's Law: accept a pasted link in any reasonable shape (extra
        # whitespace, missing "https://") and normalize it before the
        # URLField's own validation runs - otherwise a perfectly findable
        # link like "webook.com/xyz" gets rejected outright just for
        # missing a scheme, instead of being fixed up automatically.
        if self.data is not None and "webook_purchase_url" in self.data:
            raw = (self.data.get("webook_purchase_url") or "").strip()
            if raw and "://" not in raw:
                raw = f"https://{raw}"
            if raw != self.data.get("webook_purchase_url"):
                self.data = self.data.copy()
                self.data["webook_purchase_url"] = raw


class ReleaseDelayForm(forms.ModelForm):
    class Meta:
        model = Match
        fields = ["release_delay_reason", "release_delay_notes"]
        widgets = {
            "release_delay_notes": forms.Textarea(attrs={"rows": 2}),
        }


class FeedbackSubmissionForm(forms.ModelForm):
    """Quick self-service form - just enough for someone to submit an idea.
    The narrative fields (situation before/after, decision reason, status)
    are filled in later by whoever reviews it in the Control Panel."""

    class Meta:
        model = FeedbackEntry
        fields = ["title", "category", "suggestion"]
        labels = {"suggestion": "Your suggestion"}
        widgets = {
            "suggestion": forms.Textarea(attrs={"rows": 4}),
        }
