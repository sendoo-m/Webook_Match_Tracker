from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import DetailView

from ..models import Event, EventActivityLog, EventChecklistItem
from ..permissions import EventScopedQuerysetMixin, require_event_access, user_can_manage_event
from .helpers import log_event_activity


class EventDetailView(LoginRequiredMixin, EventScopedQuerysetMixin, DetailView):
    model = Event
    template_name = "events/event_detail.html"
    context_object_name = "event"

    def get_queryset(self):
        return self.filter_events_queryset(
            Event.objects.select_related("category", "category__group", "venue", "sent_to_cms_by")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        event = self.object
        context["can_edit"] = user_can_manage_event(self.request.user, event)
        context["checklist_items"] = (
            event.checklist_items.filter(is_active=True)
            .select_related("template_item__category", "completed_by")
            .order_by("template_item__category__sort_order", "template_item__sort_order", "id")
        )
        context["activity_log"] = event.activity_log.select_related("user")[:20]
        context["event_status"] = Event.Status
        return context


class EventChecklistItemUpdateView(LoginRequiredMixin, EventScopedQuerysetMixin, View):
    def post(self, request, pk, *args, **kwargs):
        item = get_object_or_404(
            EventChecklistItem.objects.select_related("event", "template_item"),
            pk=pk,
            is_active=True,
        )
        event = get_object_or_404(
            self.filter_events_queryset(Event.objects.filter(pk=item.event_id)),
            pk=item.event_id,
        )
        require_event_access(request.user, event)

        status = request.POST.get("status", item.status)
        item.status = status
        if "note" in request.POST:
            item.note = request.POST.get("note", "")
        if "delay_reason" in request.POST:
            item.delay_reason = request.POST.get("delay_reason", "")

        if status == EventChecklistItem.Status.DONE:
            item.completed_by = request.user
            item.completed_at = timezone.now()
        else:
            item.completed_by = None
            item.completed_at = None

        item.save()

        log_event_activity(
            event=item.event,
            action=EventActivityLog.Action.CHECKLIST_UPDATED,
            description=_("%(title)s updated to %(status)s.") % {"title": item.template_item.title, "status": item.status},
            user=request.user,
        )

        messages.success(request, _("Checklist item updated."))
        return redirect("events:event-detail", pk=event.pk)
