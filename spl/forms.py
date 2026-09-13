# spl/forms.py

from zoneinfo import ZoneInfo

from django import forms

from matches.models import Match

RIYADH_TZ = ZoneInfo("Asia/Riyadh")


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
