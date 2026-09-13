# checklists/views.py

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from django.views import View

from checklists.models import MatchChecklistItem
from matches.models import Match
from operations.models import MatchActivityLog
from operations.permissions import MatchScopedQuerysetMixin, require_match_access
from operations.views.helpers import (
    build_match_detail_side_context,
    checklist_item_matches_filter,
    log_match_activity,
)


class ChecklistItemNoteEditView(LoginRequiredMixin, MatchScopedQuerysetMixin, View):
    """Renders the note/delay-reason form for one checklist item, shown in
    the shared quick-view popup instead of sitting permanently open on the
    page - see checklist_item_card.html's "Note"/"Delay Reason" button."""

    def get(self, request, pk, *args, **kwargs):
        item = get_object_or_404(
            MatchChecklistItem.objects.select_related("match", "template_item"),
            pk=pk,
            is_active=True,
        )
        match = get_object_or_404(
            self.filter_matches_queryset(Match.objects.filter(pk=item.match_id)),
            pk=item.match_id,
        )
        require_match_access(request.user, match)

        html = render_to_string(
            "operations/partials/checklist_item_note_form.html",
            {"item": item, "selected_filter": request.GET.get("selected_filter", "open")},
            request=request,
        )
        return HttpResponse(html)


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
        item.status = status
        # The note/delay-reason field shown depends on the status (see
        # checklist_item_card.html) - only one of them is ever present in a
        # given submission, so only overwrite the one that was actually
        # submitted or the other would get silently blanked out.
        if "note" in request.POST:
            item.note = request.POST.get("note", "")
        if "delay_reason" in request.POST:
            item.delay_reason = request.POST.get("delay_reason", "")

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

        selected_filter = request.POST.get("selected_filter", "open")
        context = build_match_detail_side_context(match, selected_filter=selected_filter)
        context["item"] = MatchChecklistItem.objects.select_related(
            "template_item__category",
            "completed_by",
        ).get(pk=item.pk)
        context["can_edit"] = True  # this line only runs for users who just passed require_match_access

        # Card fades out on its own once it no longer belongs in the active
        # filter (e.g. marked Done while viewing "Open Only") instead of
        # staying put until the next full filter refresh - see the
        # swap:300ms + .htmx-swapping fade on .checklist-card in styles.css.
        if checklist_item_matches_filter(item.status, selected_filter):
            item_html = render_to_string("operations/partials/checklist_item_card.html", context, request=request)
        else:
            item_html = ""
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
