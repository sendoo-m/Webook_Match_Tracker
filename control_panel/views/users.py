from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.urls import reverse_lazy
from django.utils.translation import gettext as _eager
from django.utils.translation import gettext_lazy as _

from control_panel.forms import UserForm
from operations.permissions import is_super_admin

from .base import PanelCreateView, PanelListView, PanelToggleActiveView, PanelUpdateView

User = get_user_model()


class UserListView(PanelListView):
    model = User
    template_name = "control_panel/user_list.html"
    context_object_name = "users"
    ordering = ["username"]
    page_title = _("Users")
    create_url_name = "control_panel:user-create"
    create_label = _("Add User")

    def get_queryset(self):
        return super().get_queryset().prefetch_related("groups", "owned_clubs")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_impersonate"] = is_super_admin(self.request.user)
        return context


class UserCreateView(PanelCreateView):
    model = User
    form_class = UserForm
    template_name = "control_panel/user_form.html"
    success_url = reverse_lazy("control_panel:user-list")
    success_message = _("User created.")
    page_title = _("Add User")
    list_url_name = "control_panel:user-list"


class UserUpdateView(PanelUpdateView):
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
