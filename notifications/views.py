from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import ListView

from .models import Notification

NOTIFICATIONS_PAGE_SIZE = 20


class NotificationListView(LoginRequiredMixin, ListView):
    model = Notification
    template_name = "operations/notification_list.html"
    context_object_name = "notifications"
    paginate_by = NOTIFICATIONS_PAGE_SIZE

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user).select_related("match", "plan")


class NotificationMarkReadView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at"])
        next_url = request.POST.get("next") or reverse("operations:notification-list")
        return redirect(next_url)


class NotificationMarkAllReadView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        Notification.objects.filter(recipient=request.user, read_at__isnull=True).update(read_at=timezone.now())
        next_url = request.POST.get("next") or reverse("operations:notification-list")
        return redirect(next_url)


class NotificationBadgeView(LoginRequiredMixin, View):
    """Returns just the sidebar bell's inner HTML (unread count) - polled via
    the existing auto-refresh-tick custom event, matching how other
    dashboard partials already refresh without a page reload."""

    def get(self, request, *args, **kwargs):
        unread_count = Notification.objects.filter(recipient=request.user, read_at__isnull=True).count()
        html = render_to_string(
            "operations/partials/notification_badge.html",
            {"unread_notification_count": unread_count},
            request=request,
        )
        return HttpResponse(html)
