# accounts/permissions.py

from django.contrib.auth.mixins import UserPassesTestMixin

from core.permissions import is_super_admin


class SuperAdminAccessMixin(UserPassesTestMixin):
    raise_exception = True
    permission_denied_message = "Only Super Admins can log in as another user."

    def test_func(self):
        return is_super_admin(self.request.user)
