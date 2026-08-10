# operations/views/feedback.py

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, TemplateView

from control_panel.models import FeedbackEntry
from operations.forms import FeedbackSubmissionForm
from operations.templatetags.display_helpers import display_name


class FeedbackPageView(LoginRequiredMixin, TemplateView):
    template_name = "operations/feedback.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        entries = FeedbackEntry.objects.all()

        grouped = {}
        for category_value, category_label in FeedbackEntry.Category.choices:
            grouped[category_label] = entries.filter(category=category_value)

        context["grouped_entries"] = grouped
        return context


class FeedbackSubmitView(LoginRequiredMixin, CreateView):
    model = FeedbackEntry
    form_class = FeedbackSubmissionForm
    template_name = "operations/feedback_submit.html"
    success_url = reverse_lazy("operations:feedback")

    def form_valid(self, form):
        form.instance.submitted_by = display_name(self.request.user)
        form.instance.status = FeedbackEntry.Status.PENDING
        messages.success(self.request, "Thanks! Your feedback was submitted for review.")
        return super().form_valid(form)
