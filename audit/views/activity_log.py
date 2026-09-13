# audit/views/activity_log.py

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.views import View
from django.views.generic import DetailView

from matches.models import Match
from operations.permissions import MatchScopedQuerysetMixin
from operations.views.helpers import build_match_progress_context, get_match_activity_page_context

ACTIVITY_FULL_PAGE_SIZE = 20

class MatchActivityLogListView(LoginRequiredMixin, MatchScopedQuerysetMixin, View):
    def get(self, request, pk, *args, **kwargs):
        match = get_object_or_404(
            self.filter_matches_queryset(Match.objects.all()),
            pk=pk,
        )
        page_number = request.GET.get("page", 1)
        context = get_match_activity_page_context(match, page=page_number)
        return HttpResponse(
            render_to_string("operations/partials/activity_log_page.html", context, request=request)
        )


class MatchActivityView(LoginRequiredMixin, MatchScopedQuerysetMixin, DetailView):
    """Full Activity Log page - its own tab, filterable by action type, user,
    and date, with real page-number pagination. Everything the mini summary
    on Overview links out to (see activity_log_mini.html)."""

    model = Match
    template_name = "operations/match_activity.html"
    context_object_name = "match"

    def get_queryset(self):
        return self.filter_matches_queryset(
            Match.objects.select_related("home_club", "away_club", "venue", "sent_to_cms_by")
        )

    def get_context_data(self, **kwargs):
        from operations.models import MatchActivityLog

        context = super().get_context_data(**kwargs)
        match = self.object
        context["match_status"] = Match.Status
        context["active_tab"] = "activity"
        context.update(build_match_progress_context(match))

        logs = match.activity_logs.select_related("user").all()

        selected_action = self.request.GET.get("action", "")
        selected_user = self.request.GET.get("user", "")
        selected_date = self.request.GET.get("date", "")
        if selected_action:
            logs = logs.filter(action=selected_action)
        if selected_user:
            logs = logs.filter(user_id=selected_user)
        if selected_date:
            logs = logs.filter(created_at__date=selected_date)

        paginator = Paginator(logs, ACTIVITY_FULL_PAGE_SIZE)
        page_obj = paginator.get_page(self.request.GET.get("page", 1))

        User = get_user_model()
        context.update({
            "page_obj": page_obj,
            "activity_logs": page_obj.object_list,
            "action_choices": MatchActivityLog.Action.choices,
            "log_users": User.objects.filter(match_activity_logs__match=match).distinct().order_by("username"),
            "selected_action": selected_action,
            "selected_user": selected_user,
            "selected_date": selected_date,
        })
        return context
