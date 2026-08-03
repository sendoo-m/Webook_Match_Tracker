# operations/views/checklist.py

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from django.views import View

from checklists.models import MatchChecklistItem
from matches.models import Match
from operations.models import MatchActivityLog
from operations.permissions import MatchScopedQuerysetMixin, require_match_access

from .helpers import build_match_detail_side_context, log_match_activity

class ChecklistItemUpdateView(View, MatchScopedQuerysetMixin):
    def post(self, request, pk, *args, **kwargs):
        item = get_object_or_404(
            MatchChecklistItem.objects.select_related("match", "template_item__category", "completed_by"),
            pk=pk,
            is_active=True,
        )
        match = get_object_or_404(
            self.filter_matches_queryset(Match.objects.filter(pk=item.match_id)),
            pk=item.match_id,
        )
        # Being able to SEE the match (above) is not the same as being allowed
        # to edit it — Viewers can see every match but must not be able to
        # save changes. This was previously missing, letting any authenticated
        # user who could see a match edit its checklist regardless of role.
        require_match_access(request.user, match)

        status = request.POST.get("status", item.status)
        note = request.POST.get("note", "")
        delay_reason = request.POST.get("delay_reason", "")

        item.status = status
        item.note = note
        item.delay_reason = delay_reason

        if status == MatchChecklistItem.Status.DONE:
            item.completed_by = request.user
            item.completed_at = timezone.now()
        else:
            item.completed_by = None
            item.completed_at = None

        item.save()

        log_match_activity(
            match=item.match,
            action=MatchActivityLog.Action.CHECKLIST_UPDATED,
            description=f"{item.template_item.title} updated to {item.status}.",
            user=request.user,
        )

        selected_filter = request.POST.get("selected_filter", "all")
        context = build_match_detail_side_context(match, selected_filter=selected_filter)
        context["item"] = MatchChecklistItem.objects.select_related(
            "template_item__category",
            "completed_by",
        ).get(pk=item.pk)
        context["can_edit"] = True  # this line only runs for users who just passed require_match_access

        item_html = render_to_string("operations/partials/checklist_item_card.html", context, request=request)
        not_started_html = render_to_string("operations/partials/sidebar_not_started.html", context, request=request)
        in_progress_html = render_to_string("operations/partials/sidebar_in_progress.html", context, request=request)
        delayed_html = render_to_string("operations/partials/sidebar_delayed.html", context, request=request)
        progress_html = render_to_string("operations/partials/match_progress_summary.html", context, request=request)
        activity_html = render_to_string(
            "operations/partials/activity_log_timeline.html",
            {
                "match": match,
                "activity_logs": context["activity_logs"],
                "has_more_logs": context["has_more_logs"],
                "next_logs_page": context["next_logs_page"],
            },
            request=request,
        )
        return HttpResponse(item_html + progress_html + not_started_html + in_progress_html + delayed_html + activity_html)

# from django.http import HttpResponse
# from django.shortcuts import get_object_or_404
# from django.template.loader import render_to_string
# from django.utils import timezone
# from django.views import View

# from checklists.models import MatchChecklistItem
# from matches.models import Match
# from operations.models import MatchActivityLog
# from operations.permissions import MatchScopedQuerysetMixin

# from .helpers import build_match_detail_side_context, log_match_activity

# class ChecklistItemUpdateView(View, MatchScopedQuerysetMixin):
#     def post(self, request, pk, *args, **kwargs):
#         item = get_object_or_404(
#             MatchChecklistItem.objects.select_related("match", "template_item__category", "completed_by"),
#             pk=pk,
#             is_active=True,
#         )
#         self.filter_matches_queryset(Match.objects.filter(pk=item.match_id)).get(pk=item.match_id)

#         status = request.POST.get("status", item.status)
#         note = request.POST.get("note", "")
#         delay_reason = request.POST.get("delay_reason", "")

#         item.status = status
#         item.note = note
#         item.delay_reason = delay_reason

#         if status == MatchChecklistItem.Status.DONE:
#             item.completed_by = request.user
#             item.completed_at = timezone.now()
#         else:
#             item.completed_by = None
#             item.completed_at = None

#         item.save()

#         log_match_activity(
#             match=item.match,
#             action=MatchActivityLog.Action.CHECKLIST_UPDATED,
#             description=f"{item.template_item.title} updated to {item.status}.",
#             user=request.user,
#         )

#         match = item.match
#         selected_filter = request.POST.get("selected_filter", "all")
#         context = build_match_detail_side_context(match, selected_filter=selected_filter)
#         context["item"] = MatchChecklistItem.objects.select_related(
#             "template_item__category",
#             "completed_by",
#         ).get(pk=item.pk)

#         item_html = render_to_string("operations/partials/checklist_item_card.html", context, request=request)
#         not_started_html = render_to_string("operations/partials/sidebar_not_started.html", context, request=request)
#         in_progress_html = render_to_string("operations/partials/sidebar_in_progress.html", context, request=request)
#         delayed_html = render_to_string("operations/partials/sidebar_delayed.html", context, request=request)
#         progress_html = render_to_string("operations/partials/match_progress_summary.html", context, request=request)
#         activity_html = render_to_string(
#             "operations/partials/activity_log_timeline.html",
#             {
#                 "match": match,
#                 "activity_logs": context["activity_logs"],
#                 "has_more_logs": context["has_more_logs"],
#                 "next_logs_page": context["next_logs_page"],
#             },
#             request=request,
#         )
#         return HttpResponse(item_html + progress_html + not_started_html + in_progress_html + delayed_html + activity_html)
