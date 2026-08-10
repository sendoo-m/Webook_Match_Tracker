from django.urls import reverse_lazy

from control_panel.forms import FeedbackEntryForm
from control_panel.models import FeedbackEntry

from .base import PanelCreateView, PanelListView, PanelUpdateView


class FeedbackEntryListView(PanelListView):
    model = FeedbackEntry
    template_name = "control_panel/feedback_list.html"
    context_object_name = "feedback_entries"
    ordering = ["-created_at"]
    page_title = "Feedback"
    create_url_name = "control_panel:feedback-create"
    create_label = "Add Feedback"


class FeedbackEntryCreateView(PanelCreateView):
    model = FeedbackEntry
    form_class = FeedbackEntryForm
    template_name = "control_panel/feedback_form.html"
    success_url = reverse_lazy("control_panel:feedback-list")
    success_message = "Feedback entry created."
    page_title = "Add Feedback"
    list_url_name = "control_panel:feedback-list"


class FeedbackEntryUpdateView(PanelUpdateView):
    model = FeedbackEntry
    form_class = FeedbackEntryForm
    template_name = "control_panel/feedback_form.html"
    success_url = reverse_lazy("control_panel:feedback-list")
    success_message = "Feedback entry updated."
    page_title = "Edit Feedback"
    list_url_name = "control_panel:feedback-list"
