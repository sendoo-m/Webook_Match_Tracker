# operations/views/changelog.py

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView

from control_panel.models import ReleaseNote


class ChangelogView(LoginRequiredMixin, ListView):
    model = ReleaseNote
    template_name = "operations/changelog.html"
    context_object_name = "release_notes"
    ordering = ["-release_date", "-id"]
