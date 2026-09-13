# operations/forms.py

from django import forms

from control_panel.models import FeedbackEntry
from matches.models import Match


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
