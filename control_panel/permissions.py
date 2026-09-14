# control_panel/permissions.py

from django.contrib.auth.mixins import UserPassesTestMixin

from core.permissions import can_manage_control_panel, is_super_admin


class ControlPanelAccessMixin(UserPassesTestMixin):
    raise_exception = True
    permission_denied_message = "You don't have access to the control panel — your account is limited to viewing only."

    def test_func(self):
        return can_manage_control_panel(self.request.user)


class ScopedControlPanelAccessMixin(UserPassesTestMixin):
    """Broader than ControlPanelAccessMixin - also admits a Club Manager
    coordinator, for exactly the three sections that use this mixin
    (Matches, Venue Images, Venue Categories - see operations.permissions.
    can_access_limited_control_panel). Each of those views' own
    get_queryset/get_context_data narrows what a non-admin coordinator
    actually sees/can act on to their own clubs - this mixin only decides
    whether they can open the page at all."""

    raise_exception = True
    permission_denied_message = "You don't have access to the control panel — your account is limited to viewing only."

    def test_func(self):
        from operations.permissions import can_access_limited_control_panel

        return can_access_limited_control_panel(self.request.user)


class BackupAccessMixin(UserPassesTestMixin):
    """Stricter than ControlPanelAccessMixin - reuses is_super_admin
    directly (superuser or "Super Admin" group only, not Operations
    Manager) since this gates the single most destructive action in the
    system: replacing the live database and media files."""

    raise_exception = True
    permission_denied_message = "Only Super Admins can manage database backups."

    def test_func(self):
        return is_super_admin(self.request.user)