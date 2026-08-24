from zoneinfo import ZoneInfo

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from checklists.models import ChecklistCategory, ChecklistTemplateItem
from control_panel.models import FeedbackEntry, ReleaseNote
from matches.models import Club, Competition, Match, UserCompetitionAccess, Venue

User = get_user_model()

MANAGEABLE_GROUP_NAMES = ("Club Manager", "Operations Manager", "Viewer")
RIYADH_TZ = ZoneInfo("Asia/Riyadh")


class ClubForm(forms.ModelForm):
    class Meta:
        model = Club
        fields = ["name_ar", "name_en", "short_name", "logo", "owner", "is_active"]


class VenueForm(forms.ModelForm):
    class Meta:
        model = Venue
        fields = ["name_ar", "name_en", "city", "google_maps_url", "is_active"]


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


class UserForm(forms.ModelForm):
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput,
        required=False,
        help_text="Leave blank to keep the current password when editing.",
    )
    group = forms.ModelChoiceField(
        label="Role",
        queryset=Group.objects.filter(name__in=MANAGEABLE_GROUP_NAMES),
        required=True,
    )
    owned_clubs = forms.ModelMultipleChoiceField(
        label="Owned clubs",
        queryset=Club.objects.all().order_by("name_ar"),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    competitions = forms.ModelMultipleChoiceField(
        label="Section access",
        queryset=Competition.objects.filter(is_active=True).order_by("sort_order"),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["password"].help_text = "Leave blank to keep the current password."
            current_group = self.instance.groups.filter(name__in=MANAGEABLE_GROUP_NAMES).first()
            if current_group:
                self.fields["group"].initial = current_group
            self.fields["owned_clubs"].initial = Club.objects.filter(owner=self.instance)
            self.fields["competitions"].initial = Competition.objects.filter(
                user_access__user=self.instance
            )
        else:
            self.fields["password"].required = True

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get("password")
        if password:
            user.set_password(password)
        if commit:
            user.save()
            self._save_related(user)
        return user

    def _save_related(self, user):
        user.groups.set([self.cleaned_data["group"]])

        selected_clubs = set(self.cleaned_data["owned_clubs"].values_list("id", flat=True))
        for club in Club.objects.filter(owner=user).exclude(id__in=selected_clubs):
            club.owner = None
            club.save(update_fields=["owner"])
        for club in Club.objects.filter(id__in=selected_clubs):
            if club.owner_id != user.id:
                club.owner = user
                club.save(update_fields=["owner"])

        selected_competitions = self.cleaned_data["competitions"]
        UserCompetitionAccess.objects.filter(user=user).exclude(
            competition__in=selected_competitions
        ).delete()
        for competition in selected_competitions:
            UserCompetitionAccess.objects.get_or_create(user=user, competition=competition)


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
