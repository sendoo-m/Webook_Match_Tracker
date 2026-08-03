from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from control_panel.permissions import ControlPanelAccessMixin


class PanelListView(LoginRequiredMixin, ControlPanelAccessMixin, ListView):
    paginate_by = 25
    page_title = ""
    create_url_name = None
    create_label = "Add New"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = self.page_title
        context["create_label"] = self.create_label
        if self.create_url_name:
            context["create_url"] = reverse(self.create_url_name)
        return context


class PanelFormMixin:
    page_title = ""
    list_url_name = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = self.page_title
        if self.list_url_name:
            context["list_url"] = reverse(self.list_url_name)
        return context


class PanelCreateView(LoginRequiredMixin, ControlPanelAccessMixin, PanelFormMixin, SuccessMessageMixin, CreateView):
    pass


class PanelUpdateView(LoginRequiredMixin, ControlPanelAccessMixin, PanelFormMixin, SuccessMessageMixin, UpdateView):
    pass


class PanelToggleActiveView(LoginRequiredMixin, ControlPanelAccessMixin, View):
    model = None
    success_url_name = None
    active_field = "is_active"

    def post(self, request, pk, *args, **kwargs):
        obj = get_object_or_404(self.model, pk=pk)
        currently_active = getattr(obj, self.active_field)
        setattr(obj, self.active_field, not currently_active)
        obj.save(update_fields=[self.active_field])
        messages.success(
            request,
            f"{obj} {'deactivated' if currently_active else 'activated'}.",
        )
        return redirect(self.success_url_name)
