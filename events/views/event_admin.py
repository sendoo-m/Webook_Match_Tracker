from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import FormView

from ..forms import EventExportFilterForm, EventForm, EventImportForm
from ..import_export import (
    build_import_template_xlsx,
    export_events_csv,
    export_events_xlsx,
    import_events_file,
)
from ..models import Category, Event
from ..services import attach_default_checklist_items
from .base import EventsPanelAccessMixin, EventsPanelCreateView, EventsPanelListView, EventsPanelUpdateView


class EventAdminListView(EventsPanelListView):
    model = Event
    template_name = "events/panel/event_list.html"
    context_object_name = "events"
    ordering = ["-event_date", "-start_time", "-id"]
    page_title = _("Events")
    create_url_name = "events:event-create"
    create_label = _("Add Event")

    def get_queryset(self):
        queryset = super().get_queryset().select_related("category", "category__group", "venue")
        category_id = self.request.GET.get("category", "")
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["export_form"] = EventExportFilterForm()
        context["selected_category"] = self.request.GET.get("category", "")
        context["categories"] = Category.objects.filter(is_active=True).select_related("group").order_by(
            "group__sort_order", "sort_order"
        )
        return context


class EventAdminCreateView(EventsPanelCreateView):
    model = Event
    form_class = EventForm
    template_name = "events/panel/event_form.html"
    success_url = reverse_lazy("events:event-list")
    success_message = _("Event created.")
    page_title = _("Add Event")
    list_url_name = "events:event-list"

    def form_valid(self, form):
        response = super().form_valid(form)
        attach_default_checklist_items(self.object)
        return response


class EventAdminUpdateView(EventsPanelUpdateView):
    model = Event
    form_class = EventForm
    template_name = "events/panel/event_form.html"
    success_url = reverse_lazy("events:event-list")
    success_message = _("Event updated.")
    page_title = _("Edit Event")
    list_url_name = "events:event-list"


class EventExportView(LoginRequiredMixin, EventsPanelAccessMixin, View):
    def get(self, request, *args, **kwargs):
        queryset = Event.objects.all()
        category_id = request.GET.get("category")
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        if request.GET.get("format") == "csv":
            content = export_events_csv(queryset)
            response = HttpResponse(content, content_type="text/csv; charset=utf-8")
            response["Content-Disposition"] = 'attachment; filename="events_export.csv"'
        else:
            content = export_events_xlsx(queryset)
            response = HttpResponse(
                content,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = 'attachment; filename="events_export.xlsx"'
        return response


class EventTemplateView(LoginRequiredMixin, EventsPanelAccessMixin, View):
    def get(self, request, *args, **kwargs):
        content = build_import_template_xlsx()
        response = HttpResponse(
            content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="events_import_template.xlsx"'
        return response


class EventImportView(LoginRequiredMixin, EventsPanelAccessMixin, FormView):
    template_name = "events/panel/event_import.html"
    form_class = EventImportForm

    def get_success_url(self):
        return reverse("events:event-import")

    def form_valid(self, form):
        import_file = form.cleaned_data["import_file"]
        category = form.cleaned_data.get("category")
        result = import_events_file(
            import_file, import_file.name, category.id if category else None
        )
        return self.render_to_response(self.get_context_data(form=self.form_class(), result=result))
