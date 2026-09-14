# accounts/forms.py

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from matches.models import Club, Competition, UserCompetitionAccess

User = get_user_model()

MANAGEABLE_GROUP_NAMES = ("Club Manager", "Club Viewer", "Operations Manager", "Viewer", "Events Manager")


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
        label="Coordinated clubs",
        help_text="Clubs this account manages as an internal coordinator (Club Manager). A club already coordinated by someone else must be removed from their list first.",
        queryset=Club.objects.all().order_by("name_ar"),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    club_account = forms.ModelChoiceField(
        label="Club account (direct club login)",
        help_text="At most one club - this is the club's own dedicated account (Club Viewer), independent of any coordinator.",
        queryset=Club.objects.all().order_by("name_ar"),
        required=False,
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
            self.fields["club_account"].initial = Club.objects.filter(club_account=self.instance).first()
            self.fields["competitions"].initial = Competition.objects.filter(
                user_access__user=self.instance
            )
        else:
            self.fields["password"].required = True

    def clean(self):
        cleaned_data = super().clean()

        owned_clubs = cleaned_data.get("owned_clubs")
        if owned_clubs:
            taken = [
                club for club in owned_clubs
                if club.owner_id is not None and club.owner_id != self.instance.pk
            ]
            if taken:
                names = ", ".join(club.name_ar or club.name_en for club in taken)
                self.add_error(
                    "owned_clubs",
                    f"Already coordinated by another account, remove from their list first: {names}.",
                )

        club_account = cleaned_data.get("club_account")
        if club_account and club_account.club_account_id and club_account.club_account_id != self.instance.pk:
            self.add_error(
                "club_account",
                f'"{club_account.name_ar or club_account.name_en}" already has a Club Viewer account.',
            )

        return cleaned_data

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

        selected_club_account = self.cleaned_data.get("club_account")
        for club in Club.objects.filter(club_account=user).exclude(pk=getattr(selected_club_account, "pk", None)):
            club.club_account = None
            club.save(update_fields=["club_account"])
        if selected_club_account and selected_club_account.club_account_id != user.id:
            selected_club_account.club_account = user
            selected_club_account.save(update_fields=["club_account"])

        selected_competitions = self.cleaned_data["competitions"]
        UserCompetitionAccess.objects.filter(user=user).exclude(
            competition__in=selected_competitions
        ).delete()
        for competition in selected_competitions:
            UserCompetitionAccess.objects.get_or_create(user=user, competition=competition)
