from django.contrib.auth.mixins import UserPassesTestMixin

from operations.permissions import can_view_all_matches


class ControlPanelAccessMixin(UserPassesTestMixin):
    raise_exception = True

    def test_func(self):
        return can_view_all_matches(self.request.user)
