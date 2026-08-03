from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from control_panel.permissions import ControlPanelAccessMixin


class PanelHomeView(LoginRequiredMixin, ControlPanelAccessMixin, TemplateView):
    template_name = "control_panel/home.html"
