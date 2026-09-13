# control_panel/permissions.py

from django.contrib.auth.mixins import UserPassesTestMixin

from core.permissions import can_manage_control_panel, is_super_admin


class ControlPanelAccessMixin(UserPassesTestMixin):
    raise_exception = True
    permission_denied_message = "You don't have access to the control panel — your account is limited to viewing only."

    def test_func(self):
        return can_manage_control_panel(self.request.user)


class SuperAdminAccessMixin(UserPassesTestMixin):
    raise_exception = True
    permission_denied_message = "Only Super Admins can log in as another user."

    def test_func(self):
        return is_super_admin(self.request.user)