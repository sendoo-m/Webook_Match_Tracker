from django.urls import reverse_lazy

from control_panel.forms import ReleaseNoteForm
from control_panel.models import ReleaseNote

from .base import PanelCreateView, PanelListView, PanelUpdateView


class ReleaseNoteListView(PanelListView):
    model = ReleaseNote
    template_name = "control_panel/release_note_list.html"
    context_object_name = "release_notes"
    ordering = ["-release_date", "-id"]
    page_title = "What's New"
    create_url_name = "control_panel:release-note-create"
    create_label = "Add Release"


class ReleaseNoteCreateView(PanelCreateView):
    model = ReleaseNote
    form_class = ReleaseNoteForm
    template_name = "control_panel/release_note_form.html"
    success_url = reverse_lazy("control_panel:release-note-list")
    success_message = "Release note created."
    page_title = "Add Release"
    list_url_name = "control_panel:release-note-list"


class ReleaseNoteUpdateView(PanelUpdateView):
    model = ReleaseNote
    form_class = ReleaseNoteForm
    template_name = "control_panel/release_note_form.html"
    success_url = reverse_lazy("control_panel:release-note-list")
    success_message = "Release note updated."
    page_title = "Edit Release"
    list_url_name = "control_panel:release-note-list"
