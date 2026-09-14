from zoneinfo import ZoneInfo

from django import forms
from django.utils.translation import gettext_lazy as _

from checklists.models import ChecklistCategory, ChecklistTemplateItem
from control_panel.models import FeedbackEntry, ReleaseNote, SiteSettings
from matches.models import Club, Competition, Match, Venue, VenueImage, VenueSeatingCategory

RIYADH_TZ = ZoneInfo("Asia/Riyadh")


class SiteSettingsForm(forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = ["site_name_ar", "site_name_en", "logo"]


class ClubForm(forms.ModelForm):
    class Meta:
        model = Club
        fields = ["name_ar", "name_en", "short_name", "logo", "owner", "is_active"]


class VenueForm(forms.ModelForm):
    class Meta:
        model = Venue
        fields = ["name_ar", "name_en", "city", "google_maps_url", "seat_type", "is_active"]


class VenueImageForm(forms.ModelForm):
    """`venue_queryset`, when passed, restricts the venue choices - used by
    a Club Manager coordinator's scoped access to this page (see
    control_panel/views/venue_details.py), left unset for the full-admin
    path so every venue stays available there."""

    class Meta:
        model = VenueImage
        fields = ["venue", "image", "caption", "sort_order", "is_active"]

    def __init__(self, *args, venue_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        if venue_queryset is not None:
            self.fields["venue"].queryset = venue_queryset


class VenueSeatingCategoryForm(forms.ModelForm):
    """`venue_queryset`/`club_queryset`, when passed, restrict those two
    choices - same coordinator-scoping purpose as VenueImageForm above."""

    class Meta:
        model = VenueSeatingCategory
        fields = ["venue", "club", "code", "seat_count", "sort_order", "is_active"]

    def __init__(self, *args, venue_queryset=None, club_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        if venue_queryset is not None:
            self.fields["venue"].queryset = venue_queryset
        if club_queryset is not None:
            self.fields["club"].queryset = club_queryset


class VenueCategoryImportForm(forms.Form):
    venue = forms.ModelChoiceField(
        label=_("Venue"),
        queryset=Venue.objects.filter(is_active=True).order_by("name_ar"),
    )
    club = forms.ModelChoiceField(
        label=_("Club"),
        queryset=Club.objects.filter(is_active=True, is_test_club=False).order_by("name_ar"),
    )
    import_file = forms.FileField(
        label=_("Excel file"),
        help_text=_(
            'Columns: "code" (or "Ticket Name") and "seat_count" (or "Total Capacity"). '
            'A "Price" column, if present, is ignored - pricing is set per match, not here. '
            "Existing categories for this venue/club are updated by code; new codes are created."
        ),
    )

    def clean_import_file(self):
        import_file = self.cleaned_data["import_file"]
        if not import_file.name.lower().endswith(".xlsx"):
            raise forms.ValidationError(_("Please upload a .xlsx file."))
        return import_file


class CompetitionForm(forms.ModelForm):
    class Meta:
        model = Competition
        fields = ["name_ar", "name_en", "sort_order", "is_active"]


class MatchForm(forms.ModelForm):
    class Meta:
        model = Match
        fields = [
            "competition",
            "home_club",
            "away_club",
            "venue",
            "round_number",
            "slug",
            "title_ar",
            "title_en",
            "description_ar",
            "description_en",
            "event_date",
            "match_start_time",
            "match_end_time",
            "gates_open_time",
            "sale_starts_at",
            "actual_release_at",
            "ticketing_plan_approved",
            "spl_tickets_sent",
            "spl_comments",
        ]
        # actual_release_at defaults to being stamped automatically from the
        # CMS Status Control when a match is marked Published (see
        # operations/views/cms.py) - that stamp only fires once and never
        # overwrites an existing value. It's editable here too, so it can be
        # corrected or backfilled for matches published before this field
        # existed.
        widgets = {
            "event_date": forms.DateInput(attrs={"type": "date"}),
            "match_start_time": forms.TimeInput(attrs={"type": "time"}),
            "match_end_time": forms.TimeInput(attrs={"type": "time"}),
            "gates_open_time": forms.TimeInput(attrs={"type": "time"}),
            "sale_starts_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "actual_release_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "description_ar": forms.Textarea(attrs={"rows": 3}),
            "description_en": forms.Textarea(attrs={"rows": 3}),
            "spl_comments": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        home_club = cleaned.get("home_club")
        away_club = cleaned.get("away_club")
        if home_club and away_club and home_club == away_club:
            raise forms.ValidationError("Home and away clubs must be different.")
        return cleaned

    def clean_sale_starts_at(self):
        # The datetime-local widget has no offset; treat whatever wall-clock
        # value the coordinator entered as Asia/Riyadh, matching the import
        # command's convention, instead of Django's UTC default.
        value = self.cleaned_data.get("sale_starts_at")
        if value:
            return value.replace(tzinfo=RIYADH_TZ)
        return value

    def clean_actual_release_at(self):
        value = self.cleaned_data.get("actual_release_at")
        if value:
            return value.replace(tzinfo=RIYADH_TZ)
        return value


class MatchImportForm(forms.Form):
    import_file = forms.FileField(
        label="CSV or Excel file",
        help_text="Columns: slug, competition, home_club, away_club, venue, round_number, "
        "title_ar, title_en, description_ar, description_en, event_date, match_start_time, "
        "match_end_time, gates_open_time, sale_starts_at. Matches are matched/updated by slug.",
    )
    competition = forms.ModelChoiceField(
        label="Only import this section",
        queryset=Competition.objects.filter(is_active=True).order_by("sort_order", "name_ar"),
        required=False,
        help_text="Leave blank to import every row in the file. If set, rows for any other "
        "section are skipped rather than imported.",
    )

    def clean_import_file(self):
        import_file = self.cleaned_data["import_file"]
        if not import_file.name.lower().endswith((".csv", ".xlsx")):
            raise forms.ValidationError("Please upload a .csv or .xlsx file.")
        return import_file


class MatchExportFilterForm(forms.Form):
    FORMAT_CHOICES = (
        ("xlsx", "Excel (.xlsx)"),
        ("csv", "CSV"),
    )
    competition = forms.ModelChoiceField(
        label="Section",
        queryset=Competition.objects.filter(is_active=True).order_by("sort_order", "name_ar"),
        required=False,
        empty_label="All sections",
    )
    format = forms.ChoiceField(label="Format", choices=FORMAT_CHOICES, initial="xlsx")


class ChecklistCategoryForm(forms.ModelForm):
    class Meta:
        model = ChecklistCategory
        fields = ["name", "sort_order"]


class ChecklistTemplateItemForm(forms.ModelForm):
    class Meta:
        model = ChecklistTemplateItem
        fields = ["category", "title", "description", "sort_order", "is_required", "is_active"]


class FeedbackEntryForm(forms.ModelForm):
    class Meta:
        model = FeedbackEntry
        fields = [
            "title",
            "category",
            "submitted_by",
            "situation_before",
            "suggestion",
            "situation_after",
            "status",
            "decision_reason",
        ]
        widgets = {
            "situation_before": forms.Textarea(attrs={"rows": 3}),
            "suggestion": forms.Textarea(attrs={"rows": 3}),
            "situation_after": forms.Textarea(attrs={"rows": 3}),
            "decision_reason": forms.Textarea(attrs={"rows": 2}),
        }


class ReleaseNoteForm(forms.ModelForm):
    class Meta:
        model = ReleaseNote
        fields = ["version", "release_date", "highlights"]
        widgets = {
            "release_date": forms.DateInput(attrs={"type": "date"}),
            "highlights": forms.Textarea(attrs={"rows": 6, "placeholder": "One highlight per line"}),
        }
