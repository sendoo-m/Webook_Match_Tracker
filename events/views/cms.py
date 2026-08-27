from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views import View

from ..models import Event, EventActivityLog
from ..permissions import EventScopedQuerysetMixin, require_event_access
from .helpers import log_event_activity


class EventSendToCMSView(LoginRequiredMixin, EventScopedQuerysetMixin, View):
    def post(self, request, pk):
        event = get_object_or_404(self.filter_events_queryset(Event.objects.all()), pk=pk)
        require_event_access(request.user, event)

        old_status = event.cms_status
        event.refresh_checklist_status()
        event.refresh_from_db()
        if event.cms_status != Event.Status.READY_FOR_CMS:
            messages.error(request, _("Event is not ready for CMS."))
            return redirect("events:event-detail", pk=event.pk)

        event.cms_status = Event.Status.SENT_TO_CMS
        event.sent_to_cms_at = timezone.now()
        event.sent_to_cms_by = request.user
        event.save(update_fields=["cms_status", "sent_to_cms_at", "sent_to_cms_by", "updated_at"])

        log_event_activity(event=event, action=EventActivityLog.Action.SENT_TO_CMS, description=_("Event sent to CMS."), user=request.user)
        if old_status != event.cms_status:
            log_event_activity(
                event=event,
                action=EventActivityLog.Action.STATUS_CHANGED,
                description=_("Event status changed: %(old)s → %(new)s") % {"old": old_status, "new": event.cms_status},
                user=request.user,
            )

        messages.success(request, _("Event sent to CMS successfully."))
        return redirect("events:event-detail", pk=event.pk)


class EventCMSStatusUpdateView(LoginRequiredMixin, EventScopedQuerysetMixin, View):
    def post(self, request, pk, *args, **kwargs):
        event = get_object_or_404(self.filter_events_queryset(Event.objects.all()), pk=pk)
        require_event_access(request.user, event)

        new_status = request.POST.get("cms_status")
        allowed_statuses = {choice[0] for choice in Event.Status.choices}
        if new_status not in allowed_statuses:
            messages.error(request, _("Invalid CMS status."))
            return redirect("events:event-detail", pk=event.pk)

        old_status = event.cms_status
        event.cms_status = new_status
        update_fields = ["cms_status", "updated_at"]
        if new_status == Event.Status.SENT_TO_CMS:
            event.sent_to_cms_at = timezone.now()
            event.sent_to_cms_by = request.user
            update_fields.extend(["sent_to_cms_at", "sent_to_cms_by"])
        elif new_status in {Event.Status.DRAFT, Event.Status.IN_PROGRESS, Event.Status.READY_FOR_CMS}:
            event.sent_to_cms_at = None
            event.sent_to_cms_by = None
            update_fields.extend(["sent_to_cms_at", "sent_to_cms_by"])
        elif new_status == Event.Status.PUBLISHED and not event.actual_release_at:
            event.actual_release_at = timezone.now()
            update_fields.append("actual_release_at")
        event.save(update_fields=update_fields)

        old_label = dict(Event.Status.choices).get(old_status, old_status)
        new_label = dict(Event.Status.choices).get(new_status, new_status)
        if old_status != new_status:
            log_event_activity(
                event=event,
                action=EventActivityLog.Action.STATUS_CHANGED,
                description=_("CMS status changed: %(old)s → %(new)s") % {"old": old_label, "new": new_label},
                user=request.user,
            )

        messages.success(request, _("CMS status updated successfully."))
        return redirect("events:event-detail", pk=event.pk)
