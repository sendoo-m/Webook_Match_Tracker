from django.contrib.auth.mixins import UserPassesTestMixin

from control_panel.views.base import PanelCreateView, PanelListView, PanelUpdateView

from ..permissions import can_manage_events_panel


class EventsPanelAccessMixin(UserPassesTestMixin):
    raise_exception = True
    permission_denied_message = "You don't have access to the events panel — your account is limited to viewing only."

    def test_func(self):
        return can_manage_events_panel(self.request.user)


class EventsPanelListView(EventsPanelAccessMixin, PanelListView):
    pass


class EventsPanelCreateView(EventsPanelAccessMixin, PanelCreateView):
    pass


class EventsPanelUpdateView(EventsPanelAccessMixin, PanelUpdateView):
    pass
