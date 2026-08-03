from django.contrib.auth import get_user_model
from django.urls import reverse_lazy

from control_panel.forms import UserForm

from .base import PanelCreateView, PanelListView, PanelToggleActiveView, PanelUpdateView

User = get_user_model()


class UserListView(PanelListView):
    model = User
    template_name = "control_panel/user_list.html"
    context_object_name = "users"
    ordering = ["username"]
    page_title = "Users"
    create_url_name = "control_panel:user-create"
    create_label = "Add User"

    def get_queryset(self):
        return super().get_queryset().prefetch_related("groups", "owned_clubs")


class UserCreateView(PanelCreateView):
    model = User
    form_class = UserForm
    template_name = "control_panel/user_form.html"
    success_url = reverse_lazy("control_panel:user-list")
    success_message = "User created."
    page_title = "Add User"
    list_url_name = "control_panel:user-list"


class UserUpdateView(PanelUpdateView):
    model = User
    form_class = UserForm
    template_name = "control_panel/user_form.html"
    success_url = reverse_lazy("control_panel:user-list")
    success_message = "User updated."
    page_title = "Edit User"
    list_url_name = "control_panel:user-list"


class UserToggleActiveView(PanelToggleActiveView):
    model = User
    success_url_name = "control_panel:user-list"
