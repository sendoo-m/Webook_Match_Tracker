from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from control_panel.permissions import ControlPanelAccessMixin


class PanelListView(LoginRequiredMixin, ControlPanelAccessMixin, ListView):
    paginate_by = 25
    page_title = ""
    create_url_name = None
    create_label = _lazy("Add New")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = self.page_title
        context["create_label"] = self.create_label
        if self.create_url_name:
            context["create_url"] = reverse(self.create_url_name)
        querystring = self.request.GET.copy()
        querystring.pop("page", None)
        context["querystring"] = querystring.urlencode()
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

    def get_object(self, pk):
        return get_object_or_404(self.model, pk=pk)

    def get_success_url_name(self):
        """A plain string/URL by default (self.success_url_name) - override
        this instead when a subclass needs the redirect target to depend on
        who's acting (e.g. a Club Manager coordinator returning to the
        "Control Venue" hub instead of the full-admin list page)."""
        return self.success_url_name

    def post(self, request, pk, *args, **kwargs):
        obj = self.get_object(pk)
        currently_active = getattr(obj, self.active_field)
        setattr(obj, self.active_field, not currently_active)
        obj.save(update_fields=[self.active_field])
        messages.success(
            request,
            _("%(obj)s %(state)s.") % {
                "obj": obj,
                "state": _("deactivated") if currently_active else _("activated"),
            },
        )
        return redirect(self.get_success_url_name())
