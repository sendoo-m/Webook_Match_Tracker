# accounts/forms.py

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from matches.models import Club, Competition, UserCompetitionAccess

User = get_user_model()

MANAGEABLE_GROUP_NAMES = ("Club Manager", "Operations Manager", "Viewer", "Events Manager")


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
