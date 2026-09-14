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

CATEGORY_PRICE_FIELD_PREFIX = "price_"


class ClubPricingPlanUploadForm(forms.ModelForm):
    """file is optional user input (a plan can be entered purely as
    structured per-category prices, with no attached document) -
    match/club/version/status/uploaded_by are all set server-side by
    ClubPricingPlanUploadView, never from this form's data (see
    clubs/views/pricing_plan.py). One extra DecimalField per active
    VenueSeatingCategory for the match's (venue, club) is added
    dynamically in __init__, named "price_<category id>" - there is no
    formset in this codebase to reuse, and a fixed, small, per-request
    category list doesn't need one."""

    class Meta:
        model = ClubPricingPlan
        fields = ["file"]

    def __init__(self, *args, categories=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.categories = list(categories)
        for category in self.categories:
            self.fields[f"{CATEGORY_PRICE_FIELD_PREFIX}{category.id}"] = forms.DecimalField(
                label=category.code,
                required=False,
                min_value=0,
                max_digits=10,
                decimal_places=2,
            )

    def category_price_fields(self):
        """Pairs each category with its bound form field, for the
        template to render one row per category next to its reference
        seat count."""
        return [
            (category, self[f"{CATEGORY_PRICE_FIELD_PREFIX}{category.id}"])
            for category in self.categories
        ]

    def get_entered_prices(self):
        """{category_id: price} for every category field the club
        actually filled in - blank ones are simply omitted, not errors."""
        prices = {}
        for category in self.categories:
            value = self.cleaned_data.get(f"{CATEGORY_PRICE_FIELD_PREFIX}{category.id}")
            if value is not None:
                prices[category.id] = value
        return prices

    def has_any_pricing_input(self):
        return bool(self.cleaned_data.get("file")) or bool(self.get_entered_prices())


class ClubPricingPlanCategoryImportForm(forms.Form):
    import_file = forms.FileField(label="Excel file")

    def clean_import_file(self):
        import_file = self.cleaned_data["import_file"]
        if not import_file.name.lower().endswith(".xlsx"):
            raise forms.ValidationError("Please upload a .xlsx file.")
        return import_file
