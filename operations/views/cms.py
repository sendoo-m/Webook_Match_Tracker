
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views import View

from matches.models import Match
from operations.forms import WebookPurchaseLinkForm
from operations.models import MatchActivityLog
from operations.permissions import MatchScopedQuerysetMixin, require_match_access

from .helpers import (
    auto_complete_non_post_match_items,
    build_match_detail_side_context,
    build_match_progress_context,
    build_spl_report_row,
    get_match_activity_page_context,
    log_match_activity,
)

class SendToCMSView(LoginRequiredMixin, MatchScopedQuerysetMixin, View):
    def post(self, request, pk):
        match = get_object_or_404(self.filter_matches_queryset(Match.objects.select_related("home_club", "away_club", "venue", "sent_to_cms_by")), pk=pk)
        require_match_access(request.user, match)
        old_match_status = match.cms_status
        match.refresh_checklist_status()
        match.refresh_from_db()
        if match.cms_status != Match.Status.READY_FOR_CMS:
            if request.headers.get("HX-Request") == "true":
                return HttpResponseBadRequest(_("Match is not ready for CMS."))
            messages.error(request, _("Match is not ready for CMS."))
            return redirect("operations:match-detail", pk=match.pk)
        match.cms_status = Match.Status.SENT_TO_CMS
        match.sent_to_cms_at = timezone.now()
        match.sent_to_cms_by = request.user
        match.save(update_fields=["cms_status", "sent_to_cms_at", "sent_to_cms_by", "updated_at"])
        log_match_activity(match=match, action=MatchActivityLog.Action.SENT_TO_CMS, description="Match sent to CMS.", user=request.user)
        if old_match_status != match.cms_status:
            log_match_activity(match=match, action=MatchActivityLog.Action.STATUS_CHANGED, description=f"Match status changed: {old_match_status} → {match.cms_status}", user=request.user)
        match.refresh_from_db()
        activity_context = get_match_activity_page_context(match, page=1)
        if request.headers.get("HX-Request") == "true":
            progress_html = render_to_string("operations/partials/match_progress_summary.html", build_match_progress_context(match), request=request)
            status_html = render_to_string(
                "operations/partials/match_status_badge.html",
                {"match": match, "match_status": Match.Status, "can_edit": True, "today": timezone.localdate()},
                request=request,
            )
            activity_html = render_to_string("operations/partials/activity_log_timeline.html", activity_context, request=request)
            return HttpResponse(progress_html + status_html + activity_html)
        messages.success(request, _("Match sent to CMS successfully."))
        return redirect("operations:match-detail", pk=match.pk)

class MatchCMSStatusUpdateView(LoginRequiredMixin, MatchScopedQuerysetMixin, View):
    def post(self, request, pk, *args, **kwargs):
        match = get_object_or_404(self.filter_matches_queryset(Match.objects.select_related("home_club", "away_club", "venue", "sent_to_cms_by")), pk=pk)
        require_match_access(request.user, match)
        new_status = request.POST.get("cms_status")
        allowed_statuses = {choice[0] for choice in Match.Status.choices}
        if new_status not in allowed_statuses:
            if request.headers.get("HX-Request") == "true":
                return HttpResponseBadRequest(_("Invalid CMS status."))
            messages.error(request, _("Invalid CMS status."))
            return redirect("operations:match-detail", pk=match.pk)
        old_status = match.cms_status
        match.cms_status = new_status
        update_fields = ["cms_status", "updated_at"]
        if new_status == Match.Status.SENT_TO_CMS:
            match.sent_to_cms_at = timezone.now()
            match.sent_to_cms_by = request.user
            update_fields.extend(["sent_to_cms_at", "sent_to_cms_by"])
        elif new_status in {Match.Status.DRAFT, Match.Status.IN_PROGRESS, Match.Status.READY_FOR_CMS}:
            match.sent_to_cms_at = None
            match.sent_to_cms_by = None
            update_fields.extend(["sent_to_cms_at", "sent_to_cms_by"])
        elif new_status == Match.Status.PUBLISHED and not match.actual_release_at:
            # The SPL report's "Actual Release Date" is derived from this
            # control rather than typed in manually - it's the moment the
            # match actually went live, not a plan someone can edit after
            # the fact.
            match.actual_release_at = timezone.now()
            update_fields.append("actual_release_at")
        match.save(update_fields=update_fields)
        old_status_label = dict(Match.Status.choices).get(old_status, old_status)
        new_status_label = dict(Match.Status.choices).get(new_status, new_status)
        if old_status != new_status:
            log_match_activity(match=match, action=MatchActivityLog.Action.STATUS_CHANGED, description=f"CMS status changed: {old_status_label} → {new_status_label}", user=request.user)
        match.refresh_from_db()

        # Publishing a match with a ticket link already set (e.g. it was
        # entered before this status change) means every pre-match item is
        # effectively confirmed - see auto_complete_non_post_match_items.
        auto_completed = []
        if new_status == Match.Status.PUBLISHED and match.webook_purchase_url:
            auto_completed = auto_complete_non_post_match_items(match, request.user)
            if auto_completed:
                log_match_activity(
                    match=match,
                    action=MatchActivityLog.Action.CHECKLIST_UPDATED,
                    description=f"{len(auto_completed)} pre-match checklist item(s) auto-completed on publish.",
                    user=request.user,
                )

        detail_context = build_match_detail_side_context(match)
        detail_context["match_status"] = Match.Status
        detail_context["today"] = timezone.localdate()
        detail_context["can_edit"] = True  # this view already required require_match_access above
        detail_context.update(get_match_activity_page_context(match, page=1))
        progress_html = render_to_string("operations/partials/match_progress_summary.html", detail_context, request=request)
        status_html = render_to_string("operations/partials/match_status_badge.html", detail_context, request=request)
        activity_html = render_to_string("operations/partials/activity_log_timeline.html", detail_context, request=request)
        # This form posts with hx-swap="none" (see match_status_badge.html) and
        # relies entirely on out-of-band swaps, so this fragment needs the oob
        # attribute here - unlike its own Edit/Save actions, which target and
        # swap this same box directly.
        spl_info_html = render_to_string(
            "operations/partials/match_spl_info_box.html",
            {"match": match, "can_edit": True, "oob": True, **build_spl_report_row(match, timezone.localtime())},
            request=request,
        )
        response_html = progress_html + status_html + activity_html
        if request.headers.get("HX-Request") == "true":
            response = HttpResponse(response_html + spl_info_html)
            if auto_completed:
                # The checklist cards themselves aren't part of this
                # response (only the status/progress/sidebar boxes are) -
                # a full refresh is the simplest way to guarantee every
                # auto-completed item's card reflects its new status too,
                # instead of only patching the summary numbers.
                response["HX-Refresh"] = "true"
            return response
        messages.success(request, _("CMS status updated successfully."))
        return redirect("operations:match-detail", pk=match.pk)


class MatchWebookLinkUpdateView(LoginRequiredMixin, MatchScopedQuerysetMixin, View):
    """Sets the public webook.com ticket purchase link shown on the Match
    Status panel once a match is Published/live - same permission gate
    (require_match_access) as the other CMS status actions on that panel."""

    def post(self, request, pk, *args, **kwargs):
        match = get_object_or_404(self.filter_matches_queryset(Match.objects.all()), pk=pk)
        require_match_access(request.user, match)

        form = WebookPurchaseLinkForm(request.POST, instance=match)
        if not form.is_valid():
            error_text = " ".join(str(error) for errors in form.errors.values() for error in errors)
            if request.headers.get("HX-Request") == "true":
                # A normal messages.error() here would be silently lost -
                # this response is an htmx partial swap, not a full page
                # render, so the messages block in base.html never sees it.
                return HttpResponseBadRequest(error_text or _("Could not update the link."))
            messages.error(request, error_text or _("Could not update the link."))
            return redirect("operations:match-detail", pk=match.pk)

        form.save()
        log_match_activity(
            match=match,
            action=MatchActivityLog.Action.STATUS_CHANGED,
            description="Webook purchase link updated.",
            user=request.user,
        )
        messages.success(request, _("Webook purchase link updated."))

        match.refresh_from_db()

        # This is the common order in practice: publish first (the link
        # field only appears once Published), then paste the link - so
        # this is where auto_complete_non_post_match_items usually fires.
        auto_completed = []
        if match.cms_status == Match.Status.PUBLISHED and match.webook_purchase_url:
            auto_completed = auto_complete_non_post_match_items(match, request.user)
            if auto_completed:
                log_match_activity(
                    match=match,
                    action=MatchActivityLog.Action.CHECKLIST_UPDATED,
                    description=f"{len(auto_completed)} pre-match checklist item(s) auto-completed on publish.",
                    user=request.user,
                )

        detail_context = build_match_detail_side_context(match)
        detail_context["match_status"] = Match.Status
        detail_context["today"] = timezone.localdate()
        detail_context["can_edit"] = True
        status_html = render_to_string("operations/partials/match_status_badge.html", detail_context, request=request)
        if request.headers.get("HX-Request") == "true":
            response = HttpResponse(status_html)
            if auto_completed:
                # Same reasoning as MatchCMSStatusUpdateView - the checklist
                # item cards aren't part of this response, so a full
                # refresh is the simplest way to keep them in sync.
                response["HX-Refresh"] = "true"
            return response
        return redirect("operations:match-detail", pk=match.pk)
