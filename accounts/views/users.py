# accounts/views/users.py

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.urls import reverse_lazy
from django.utils.translation import gettext as _eager
from django.utils.translation import gettext_lazy as _

from control_panel.views.base import (
    PanelCreateView,
    PanelListView,
    PanelToggleActiveView,
    PanelUpdateView,
)
from core.permissions import is_super_admin
from matches.models import Club

from ..forms import MANAGEABLE_GROUP_NAMES, UserForm

User = get_user_model()


class UserListView(PanelListView):
    """Search/filter are plain GET-param queryset filters on already-
    indexed/small tables (users, groups, clubs) - no extra queries beyond
    the two prefetches already here, and the filter dropdowns themselves
    (groups, clubs) are cheap, cached-per-request lookups."""

    model = User
    template_name = "control_panel/user_list.html"
    context_object_name = "users"
    ordering = ["username"]
    page_title = _("Users")
    create_url_name = "control_panel:user-create"
    create_label = _("Add User")

    def get_queryset(self):
        queryset = super().get_queryset().prefetch_related(
            "groups", "owned_clubs", "competition_access"
        ).select_related("own_club")

        search = self.request.GET.get("q", "").strip()
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
            )

        role = self.request.GET.get("role", "").strip()
        if role:
            queryset = queryset.filter(groups__id=role)

        club = self.request.GET.get("club", "").strip()
        if club:
            queryset = queryset.filter(Q(owned_clubs__id=club) | Q(own_club__id=club))

        status = self.request.GET.get("status", "").strip()
        if status == "active":
            queryset = queryset.filter(is_active=True)
        elif status == "inactive":
            queryset = queryset.filter(is_active=False)

        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_impersonate"] = is_super_admin(self.request.user)
        context["role_choices"] = Group.objects.filter(name__in=MANAGEABLE_GROUP_NAMES).order_by("name")
        context["club_choices"] = Club.objects.filter(is_active=True).order_by("name_ar")
        context["selected_q"] = self.request.GET.get("q", "")
        context["selected_role"] = self.request.GET.get("role", "")
        context["selected_club"] = self.request.GET.get("club", "")
        context["selected_status"] = self.request.GET.get("status", "")
        context["has_active_filters"] = any([
            context["selected_q"], context["selected_role"], context["selected_club"], context["selected_status"],
        ])
        return context


class RoleSummaryContextMixin:
    """Feeds the Add/Edit User form's client-side role-description/review-
    summary script (static/operations/js/user-role-summary.js) with
    already-translated strings via json_script, instead of the script
    hardcoding its own text - a hardcoded string in a .js file bypasses
    Django's i18n entirely and would show identically regardless of the
    active language."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["role_info"] = {
            "Club Manager": {
                "description": _(
                    "Internal coordinator - manages matches and checklists for the clubs assigned "
                    "below (access scope), and needs a granted section for each club to see its matches."
                ),
                "sensitive": False,
            },
            "Club Viewer": {
                "description": _(
                    "The club's own direct account - only sees its Club Dashboard, Release Schedule "
                    "and Calendar, and can't open the general Operations Dashboard or the full match list."
                ),
                "sensitive": False,
            },
            "Operations Manager": {
                "description": _(
                    "Full administrative access - the entire Control Panel (clubs, venues, "
                    "competitions, users, checklist templates) and every match, plus approving or "
                    "rejecting pricing plans in SPL."
                ),
                "sensitive": True,
                "reasons": [
                    _("Full access to the Control Panel"),
                    _("Can approve or reject pricing plans in SPL"),
                ],
            },
            "Viewer": {
                "description": _(
                    "SPL's own follow-up role - sees every match for monitoring, and also has the "
                    'power to approve/reject pricing plans and confirm tickets, despite being named a '
                    '"view only" role.'
                ),
                "sensitive": True,
                "reasons": [
                    _("Can approve or reject pricing plans in SPL"),
                    _("Can confirm complimentary tickets"),
                ],
            },
            "Events Manager": {
                "description": _(
                    "Events manager - an entirely separate scope from football matches; permissions "
                    "only apply to the events and categories assigned in the Events app."
                ),
                "sensitive": False,
            },
        }
        context["ui_strings"] = {
            "none": _("None"),
            "active": _("Active"),
            "inactive": _("Inactive"),
            "listSeparator": _(", "),
            "andOthers": _("and {count} others"),
        }
        return context


class UserCreateView(RoleSummaryContextMixin, PanelCreateView):
    model = User
    form_class = UserForm
    template_name = "control_panel/user_form.html"
    success_url = reverse_lazy("control_panel:user-list")
    success_message = _("User created.")
    page_title = _("Add User")
    list_url_name = "control_panel:user-list"


class UserUpdateView(RoleSummaryContextMixin, PanelUpdateView):
    model = User
    form_class = UserForm
    template_name = "control_panel/user_form.html"
    success_url = reverse_lazy("control_panel:user-list")
    success_message = _("User updated.")
    page_title = _("Edit User")
    list_url_name = "control_panel:user-list"

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if obj.is_superuser:
            raise PermissionDenied(_eager("Superuser accounts are protected and can't be edited here."))
        return obj


class UserToggleActiveView(PanelToggleActiveView):
    model = User
    success_url_name = "control_panel:user-list"

    def get_object(self, pk):
        obj = super().get_object(pk)
        if obj.is_superuser:
            raise PermissionDenied(_eager("Superuser accounts are protected and can't be activated or deactivated here."))
        return obj
