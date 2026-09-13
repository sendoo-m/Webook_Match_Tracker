# clubs/forms.py
#
# ClubPricingPlan itself stays defined in operations/models.py - moving a
# model between apps means rewriting its migration history (ContentTypes,
# the CreateModel/AddField operations already applied to the real database
# say app_label="operations"), which is a separate, much riskier step than
# moving the views/forms/templates built around it. See the architecture
# study: keep the model in place, organize the domain logic around it.

from django import forms

from operations.models import ClubPricingPlan


class ClubPricingPlanUploadForm(forms.ModelForm):
    """Only the file is user input - match/club/version/status/uploaded_by
    are all set server-side by ClubPricingPlanUploadView, never from this
    form's data (see clubs/views/pricing_plan.py)."""

    class Meta:
        model = ClubPricingPlan
        fields = ["file"]
