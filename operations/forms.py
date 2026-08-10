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


class MatchSPLInfoForm(forms.ModelForm):
    class Meta:
        model = Match
        # actual_release_at is NOT here on purpose: it's stamped automatically
        # from the CMS Status Control when a match is marked Published (see
        # operations/views/cms.py), not typed in manually.
        fields = ["ticketing_plan_approved", "spl_tickets_sent", "spl_comments"]
        widgets = {
            "spl_comments": forms.Textarea(attrs={"rows": 3}),
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
