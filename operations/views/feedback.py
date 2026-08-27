# operations/views/feedback.py

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils.translation import gettext as _
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
    """Doubles as a full standalone page AND the form loaded into the
    feedback FAB's popup modal (see base.html) - the HX-Request header tells
    us which one to render."""

    model = FeedbackEntry
    form_class = FeedbackSubmissionForm
    template_name = "operations/feedback_submit.html"
    success_url = reverse_lazy("operations:feedback")

    def get(self, request, *args, **kwargs):
        if request.headers.get("HX-Request") == "true":
            self.object = None
            form = self.get_form()
            html = render_to_string(
                "operations/partials/feedback_modal_form.html", {"form": form}, request=request
            )
            return HttpResponse(html)
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.submitted_by = display_name(self.request.user)
        form.instance.status = FeedbackEntry.Status.PENDING
        response = super().form_valid(form)
        if self.request.headers.get("HX-Request") == "true":
            return HttpResponse(render_to_string("operations/partials/feedback_modal_success.html", {}, request=self.request))
        messages.success(self.request, _("Thanks! Your feedback was submitted for review."))
        return response

    def form_invalid(self, form):
        if self.request.headers.get("HX-Request") == "true":
            html = render_to_string(
                "operations/partials/feedback_modal_form.html", {"form": form}, request=self.request
            )
            return HttpResponse(html)
        return super().form_invalid(form)
