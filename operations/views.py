# File: operations/views.py
# Path: config/operations/views.py

from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from checklists.models import MatchChecklistItem
from matches.models import Club, Match

from .models import MatchActivityLog

POST_MATCH_CATEGORY_NAME = "Post Match"
LIVE_MATCH_DURATION_HOURS = 2
PREP_WINDOW_DAYS = 20
STARTING_SOON_HOURS = 48
ACTIVITY_LOG_PAGE_SIZE = 8


def combine_match_datetime(match):
    if not match.event_date:
        return None

    start_time = getattr(match, "match_start_time", None)
    if start_time:
        dt = datetime.combine(match.event_date, start_time)
    else:
        dt = datetime.combine(match.event_date, datetime.min.time())

    if timezone.is_naive(dt):
        return timezone.make_aware(dt)
    return dt

def build_dashboard_match_state(match, now=None):
    now = now or timezone.localtime()
    match_dt = combine_match_datetime(match)

    checklist_qs = match.checklist_items.filter(is_active=True)
    post_match_qs = checklist_qs.filter(
        template_item__category__name=POST_MATCH_CATEGORY_NAME
    )
    non_post_match_qs = checklist_qs.exclude(
        template_item__category__name=POST_MATCH_CATEGORY_NAME
    )

    total_items = checklist_qs.count()
    done_items = checklist_qs.filter(status=MatchChecklistItem.Status.DONE).count()
    delayed_items = checklist_qs.filter(status=MatchChecklistItem.Status.DELAYED).count()
    in_progress_items = checklist_qs.filter(status=MatchChecklistItem.Status.IN_PROGRESS).count()
    not_started_items = checklist_qs.filter(status=MatchChecklistItem.Status.NOT_STARTED).count()

    post_match_total = post_match_qs.count()
    post_match_done = post_match_qs.filter(status=MatchChecklistItem.Status.DONE).count()
    post_match_pending = post_match_total - post_match_done

    non_post_match_total = non_post_match_qs.count()
    non_post_match_done = non_post_match_qs.filter(status=MatchChecklistItem.Status.DONE).count()
    non_post_match_pending = non_post_match_total - non_post_match_done

    days_to_match = None
    hours_to_match = None
    prep_window_started = False
    is_today = False
    is_past = False
    starting_within_48h = False

    if match_dt:
        local_match_dt = timezone.localtime(match_dt)
        diff = local_match_dt - now
        hours_to_match = diff.total_seconds() / 3600
        days_to_match = (local_match_dt.date() - now.date()).days

        prep_window_started = days_to_match <= PREP_WINDOW_DAYS
        is_today = local_match_dt.date() == now.date()
        is_past = local_match_dt < now
        starting_within_48h = 0 <= hours_to_match <= STARTING_SOON_HOURS

    ready_for_ticket_sale = (
        non_post_match_total > 0 and
        non_post_match_pending == 0
    )

    published_is_live = match.cms_status == Match.Status.PUBLISHED

    auto_live_by_ops = (
        not is_past and
        prep_window_started and
        non_post_match_total > 0 and
        non_post_match_pending == 0
    )

    is_live_now = published_is_live or auto_live_by_ops

    needs_reports = is_past and post_match_pending > 0

    if is_live_now:
        alert_level = "success"
        if published_is_live:
            alert_text = "Live on CMS"
        else:
            alert_text = "Live by Schedule"
    elif days_to_match is None:
        alert_level = "neutral"
        alert_text = "Missing match date"
    elif needs_reports:
        alert_level = "danger"
        alert_text = "Reports Pending"
    elif ready_for_ticket_sale and not is_past:
        alert_level = "success"
        alert_text = "Ready for Ticket Sale"
    elif days_to_match <= 2 and non_post_match_pending > 0:
        alert_level = "danger"
        alert_text = "Critical Prep"
    elif days_to_match <= 5 and non_post_match_pending > 0:
        alert_level = "warning"
        alert_text = "Urgent Prep"
    elif days_to_match <= 10 and non_post_match_pending > 0:
        alert_level = "warning"
        alert_text = "Needs Attention"
    elif days_to_match <= PREP_WINDOW_DAYS and non_post_match_pending > 0:
        alert_level = "info"
        alert_text = "Prep Window Started"
    else:
        alert_level = "neutral"
        alert_text = "On Track"

    return {
        "match": match,
        "match_dt": match_dt,
        "days_to_match": days_to_match,
        "hours_to_match": hours_to_match,
        "prep_window_started": prep_window_started,
        "is_today": is_today,
        "is_past": is_past,
        "is_live_now": is_live_now,
        "starting_within_48h": starting_within_48h,
        "ready_for_ticket_sale": ready_for_ticket_sale,
        "needs_reports": needs_reports,
        "published_is_live": published_is_live,
        "auto_live_by_ops": auto_live_by_ops,
        "alert_level": alert_level,
        "alert_text": alert_text,
        "total_items": total_items,
        "done_items": done_items,
        "delayed_items": delayed_items,
        "in_progress_items": in_progress_items,
        "not_started_items": not_started_items,
        "post_match_total": post_match_total,
        "post_match_done": post_match_done,
        "post_match_pending": post_match_pending,
        "non_post_match_total": non_post_match_total,
        "non_post_match_done": non_post_match_done,
        "non_post_match_pending": non_post_match_pending,
    }

def build_match_progress_context(match):
    active_items = match.checklist_items.filter(is_active=True)
    required_items = active_items.filter(template_item__is_required=True)

    total_items = active_items.count()
    done_items = active_items.filter(status=MatchChecklistItem.Status.DONE).count()
    delayed_items = active_items.filter(status=MatchChecklistItem.Status.DELAYED).count()
    not_started_items = active_items.filter(status=MatchChecklistItem.Status.NOT_STARTED).count()
    in_progress_items = active_items.filter(status=MatchChecklistItem.Status.IN_PROGRESS).count()

    required_total = required_items.count()
    required_done = required_items.filter(status=MatchChecklistItem.Status.DONE).count()
    required_delayed = required_items.filter(status=MatchChecklistItem.Status.DELAYED).count()

    progress_percent = 0
    if total_items > 0:
        progress_percent = round((done_items / total_items) * 100)

    return {
        "match": match,
        "total_items": total_items,
        "done_items": done_items,
        "delayed_items": delayed_items,
        "not_started_count": not_started_items,
        "in_progress_count": in_progress_items,
        "required_total": required_total,
        "required_done": required_done,
        "required_delayed": required_delayed,
        "progress_percent": progress_percent,
    }


def get_match_activity_page_context(match, page=1, per_page=ACTIVITY_LOG_PAGE_SIZE):
    logs_qs = match.activity_logs.select_related("user").all().order_by("-created_at", "-id")
    paginator = Paginator(logs_qs, per_page)
    page_obj = paginator.get_page(page)

    return {
        "match": match,
        "page_obj": page_obj,
        "activity_logs": page_obj.object_list,
        "has_more_logs": page_obj.has_next(),
        "next_logs_page": page_obj.next_page_number() if page_obj.has_next() else None,
    }


def build_match_detail_side_context(match, selected_filter="all"):
    checklist_items = (
        match.checklist_items.select_related(
            "template_item__category",
            "completed_by",
        )
        .filter(is_active=True)
        .annotate(
            status_priority=Case(
                When(status=MatchChecklistItem.Status.NOT_STARTED, then=Value(0)),
                When(status=MatchChecklistItem.Status.IN_PROGRESS, then=Value(1)),
                When(status=MatchChecklistItem.Status.DELAYED, then=Value(2)),
                When(status=MatchChecklistItem.Status.DONE, then=Value(3)),
                default=Value(9),
                output_field=IntegerField(),
            )
        )
        .order_by(
            "template_item__category__sort_order",
            "status_priority",
            "template_item__sort_order",
            "id",
        )
    )

    all_items = checklist_items

    if selected_filter == "not_started":
        checklist_items = checklist_items.filter(status=MatchChecklistItem.Status.NOT_STARTED)
    elif selected_filter == "in_progress":
        checklist_items = checklist_items.filter(status=MatchChecklistItem.Status.IN_PROGRESS)
    elif selected_filter == "delayed":
        checklist_items = checklist_items.filter(status=MatchChecklistItem.Status.DELAYED)
    elif selected_filter == "done":
        checklist_items = checklist_items.filter(status=MatchChecklistItem.Status.DONE)
    elif selected_filter == "open":
        checklist_items = checklist_items.exclude(status=MatchChecklistItem.Status.DONE)

    grouped = {}
    for checklist_item in checklist_items:
        category = checklist_item.template_item.category
        grouped.setdefault(category, []).append(checklist_item)

    context = {
        "match": match,
        "grouped_checklist": grouped,
        "selected_filter": selected_filter,
        "not_started_items": all_items.filter(status=MatchChecklistItem.Status.NOT_STARTED),
        "in_progress_items": all_items.filter(status=MatchChecklistItem.Status.IN_PROGRESS),
        "delayed_items_list": all_items.filter(status=MatchChecklistItem.Status.DELAYED),
    }
    context.update(build_match_progress_context(match))
    context.update(get_match_activity_page_context(match, page=1))
    return context


def log_match_activity(match, action, description, user=None):
    MatchActivityLog.objects.create(
        match=match,
        user=user if getattr(user, "is_authenticated", False) else None,
        action=action,
        description=description,
    )


class OperationsDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "operations/dashboard.html"

    def get_template_names(self):
        if self.request.headers.get("HX-Request") == "true":
            return ["operations/partials/dashboard_filtered_matches_panel.html"]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        now = timezone.localtime()
        selected_view = self.request.GET.get("view", "all")

        matches = (
            Match.objects.all()
            .order_by("event_date", "match_start_time")
            .prefetch_related("checklist_items__template_item__category")
        )

        match_cards = [build_dashboard_match_state(match, now=now) for match in matches]

        live_matches = [c for c in match_cards if c["is_live_now"]]

        upcoming_matches = [
            c for c in match_cards
            if c["days_to_match"] is not None and c["days_to_match"] >= 0
        ]

        past_matches = [
            c for c in match_cards
            if c["days_to_match"] is not None and c["days_to_match"] < 0
        ]

        ready_for_ticket_sale_matches = [
            c for c in upcoming_matches
            if c["ready_for_ticket_sale"] and not c["is_live_now"]
        ]

        prep_alert_matches = [
            c for c in upcoming_matches
            if c["prep_window_started"] and c["non_post_match_pending"] > 0
        ]

        matches_needing_reports = [
            c for c in past_matches
            if c["needs_reports"]
        ]

        starting_soon_matches = [
            c for c in upcoming_matches
            if c["starting_within_48h"]
        ]

        upcoming_matches = sorted(
            upcoming_matches,
            key=lambda x: (
                x["days_to_match"] if x["days_to_match"] is not None else 9999,
                x["match"].match_start_time or datetime.min.time(),
            )
        )

        past_matches = sorted(
            past_matches,
            key=lambda x: x["match"].event_date or datetime.min.date(),
            reverse=True,
        )

        if selected_view == "live":
            featured_matches = live_matches
        elif selected_view == "ready":
            featured_matches = ready_for_ticket_sale_matches
        elif selected_view == "alerts":
            featured_matches = prep_alert_matches
        elif selected_view == "reports":
            featured_matches = matches_needing_reports
        elif selected_view == "upcoming":
            featured_matches = upcoming_matches
        elif selected_view == "past":
            featured_matches = past_matches
        else:
            featured_matches = upcoming_matches

        stats = {
            "total_matches": len(match_cards),
            "live_matches": len(live_matches),
            "upcoming_matches": len(upcoming_matches),
            "past_matches": len(past_matches),
            "ready_for_ticket_sale_matches": len(ready_for_ticket_sale_matches),
            "prep_alert_matches": len(prep_alert_matches),
            "matches_needing_reports": len(matches_needing_reports),
            "delayed_matches": len([c for c in match_cards if c["delayed_items"] > 0]),
            "starting_soon_matches": len(starting_soon_matches),
        }

        context.update({
            "stats": stats,
            "now": now,
            "prep_window_days": PREP_WINDOW_DAYS,
            "selected_view": selected_view,
            "live_matches": live_matches[:8],
            "ready_for_ticket_sale_matches": ready_for_ticket_sale_matches[:8],
            "prep_alert_matches": prep_alert_matches[:8],
            "starting_soon_matches": starting_soon_matches[:8],
            "matches_needing_reports": matches_needing_reports[:8],
            "upcoming_matches": upcoming_matches[:12],
            "past_matches": past_matches[:12],
            "featured_matches": featured_matches[:12],
        })
        return context

class MatchListView(LoginRequiredMixin, ListView):
    model = Match
    template_name = "operations/match_list.html"
    context_object_name = "matches"
    paginate_by = 25

    def get_queryset(self):
        qs = (
            Match.objects.select_related("home_club", "away_club", "venue", "sent_to_cms_by")
            .annotate(
                total_items=Count(
                    "checklist_items",
                    filter=Q(checklist_items__is_active=True),
                ),
                done_items=Count(
                    "checklist_items",
                    filter=Q(
                        checklist_items__status=MatchChecklistItem.Status.DONE,
                        checklist_items__is_active=True,
                    ),
                ),
                delayed_items=Count(
                    "checklist_items",
                    filter=Q(
                        checklist_items__status=MatchChecklistItem.Status.DELAYED,
                        checklist_items__is_active=True,
                    ),
                ),
            )
            .order_by("event_date", "match_start_time", "id")
        )

        status = self.request.GET.get("status")
        club = self.request.GET.get("club")

        if status:
            qs = qs.filter(cms_status=status)

        if club:
            qs = qs.filter(Q(home_club__id=club) | Q(away_club__id=club))

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["clubs"] = Club.objects.filter(is_active=True).order_by("name_ar")
        context["status_choices"] = Match.Status.choices
        context["selected_status"] = self.request.GET.get("status", "")
        context["selected_club"] = self.request.GET.get("club", "")
        return context


class MatchDetailView(DetailView):
    model = Match
    template_name = "operations/match_detail.html"
    context_object_name = "match"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        selected_filter = self.request.GET.get("filter", "all")
        context["match_status"] = Match.Status
        context.update(build_match_detail_side_context(self.object, selected_filter=selected_filter))
        return context


class ChecklistItemUpdateView(View):
    def post(self, request, pk, *args, **kwargs):
        item = get_object_or_404(
            MatchChecklistItem.objects.select_related(
                "match",
                "template_item__category",
                "completed_by",
            ),
            pk=pk,
            is_active=True,
        )

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

        match = item.match
        selected_filter = request.POST.get("selected_filter", "all")
        context = build_match_detail_side_context(match, selected_filter=selected_filter)
        context["item"] = MatchChecklistItem.objects.select_related(
            "template_item__category",
            "completed_by",
        ).get(pk=item.pk)

        item_html = render_to_string(
            "operations/partials/checklist_item_card.html",
            context,
            request=request,
        )

        not_started_html = render_to_string(
            "operations/partials/sidebar_not_started.html",
            context,
            request=request,
        )

        in_progress_html = render_to_string(
            "operations/partials/sidebar_in_progress.html",
            context,
            request=request,
        )

        delayed_html = render_to_string(
            "operations/partials/sidebar_delayed.html",
            context,
            request=request,
        )

        progress_html = render_to_string(
            "operations/partials/match_progress_summary.html",
            context,
            request=request,
        )

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

        response_html = (
            item_html
            + progress_html
            + not_started_html
            + in_progress_html
            + delayed_html
            + activity_html
        )

        return HttpResponse(response_html)


class SendToCMSView(LoginRequiredMixin, View):
    def post(self, request, pk):
        match = get_object_or_404(
            Match.objects.select_related(
                "home_club",
                "away_club",
                "venue",
                "sent_to_cms_by",
            ),
            pk=pk,
        )

        old_match_status = match.cms_status

        match.refresh_checklist_status()
        match.refresh_from_db()

        if match.cms_status != Match.Status.READY_FOR_CMS:
            if request.headers.get("HX-Request") == "true":
                return HttpResponseBadRequest("Match is not ready for CMS.")
            messages.error(request, "Match is not ready for CMS.")
            return redirect("operations:match-detail", pk=match.pk)

        match.cms_status = Match.Status.SENT_TO_CMS
        match.sent_to_cms_at = timezone.now()
        match.sent_to_cms_by = request.user
        match.save(update_fields=["cms_status", "sent_to_cms_at", "sent_to_cms_by", "updated_at"])

        log_match_activity(
            match=match,
            action=MatchActivityLog.Action.SENT_TO_CMS,
            description="Match sent to CMS.",
            user=request.user,
        )

        if old_match_status != match.cms_status:
            log_match_activity(
                match=match,
                action=MatchActivityLog.Action.STATUS_CHANGED,
                description=f"Match status changed: {old_match_status} → {match.cms_status}",
                user=request.user,
            )

        match.refresh_from_db()
        activity_context = get_match_activity_page_context(match, page=1)

        if request.headers.get("HX-Request") == "true":
            progress_html = render_to_string(
                "operations/partials/match_progress_summary.html",
                build_match_progress_context(match),
                request=request,
            )
            status_html = render_to_string(
                "operations/partials/match_status_badge.html",
                {"match": match, "match_status": Match.Status},
                request=request,
            )
            activity_html = render_to_string(
                "operations/partials/activity_log_timeline.html",
                activity_context,
                request=request,
            )
            return HttpResponse(progress_html + status_html + activity_html)

        messages.success(request, "Match sent to CMS successfully.")
        return redirect("operations:match-detail", pk=match.pk)

def refresh_checklist_status(self):
    from checklists.models import MatchChecklistItem

    active_items = self.checklist_items.filter(is_active=True)

    pre_match_items = active_items.exclude(
        template_item__category__name="Post Match"
    )
    required_pre_match_items = pre_match_items.filter(
        template_item__is_required=True
    )

    total_active = active_items.count()
    done_active = active_items.filter(
        status=MatchChecklistItem.Status.DONE
    ).count()
    delayed_active = active_items.filter(
        status=MatchChecklistItem.Status.DELAYED
    ).count()

    required_pre_total = required_pre_match_items.count()
    required_pre_done = required_pre_match_items.filter(
        status=MatchChecklistItem.Status.DONE
    ).count()
    required_pre_delayed = required_pre_match_items.filter(
        status=MatchChecklistItem.Status.DELAYED
    ).count()

    if self.cms_status in {self.Status.SENT_TO_CMS, self.Status.PUBLISHED}:
        return self

    if total_active == 0:
        new_status = self.Status.DRAFT
    elif (
        required_pre_total > 0
        and required_pre_done == required_pre_total
        and required_pre_delayed == 0
    ):
        new_status = self.Status.READY_FOR_CMS
    elif delayed_active > 0:
        new_status = self.Status.IN_PROGRESS
    elif done_active > 0:
        new_status = self.Status.IN_PROGRESS
    else:
        new_status = self.Status.DRAFT

    if self.cms_status != new_status:
        self.cms_status = new_status
        self.save(update_fields=["cms_status", "updated_at"])

    return self

class MatchActivityLogListView(LoginRequiredMixin, View):
    def get(self, request, pk, *args, **kwargs):
        match = get_object_or_404(Match, pk=pk)
        page_number = request.GET.get("page", 1)
        context = get_match_activity_page_context(match, page=page_number)

        return HttpResponse(
            render_to_string(
                "operations/partials/activity_log_page.html",
                context,
                request=request,
            )
        )

class MatchCMSStatusUpdateView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        match = get_object_or_404(
            Match.objects.select_related(
                "home_club",
                "away_club",
                "venue",
                "sent_to_cms_by",
            ),
            pk=pk,
        )

        new_status = request.POST.get("cms_status")
        allowed_statuses = {choice[0] for choice in Match.Status.choices}

        if new_status not in allowed_statuses:
            if request.headers.get("HX-Request") == "true":
                return HttpResponseBadRequest("Invalid CMS status.")
            messages.error(request, "Invalid CMS status.")
            return redirect("operations:match-detail", pk=match.pk)

        old_status = match.cms_status

        match.cms_status = new_status
        update_fields = ["cms_status", "updated_at"]

        if new_status == Match.Status.SENT_TO_CMS:
            match.sent_to_cms_at = timezone.now()
            match.sent_to_cms_by = request.user
            update_fields.extend(["sent_to_cms_at", "sent_to_cms_by"])
        elif new_status in {
            Match.Status.DRAFT,
            Match.Status.IN_PROGRESS,
            Match.Status.READY_FOR_CMS,
        }:
            match.sent_to_cms_at = None
            match.sent_to_cms_by = None
            update_fields.extend(["sent_to_cms_at", "sent_to_cms_by"])

        match.save(update_fields=update_fields)

        old_status_label = dict(Match.Status.choices).get(old_status, old_status)
        new_status_label = dict(Match.Status.choices).get(new_status, new_status)

        if old_status != new_status:
            log_match_activity(
                match=match,
                action=MatchActivityLog.Action.STATUS_CHANGED,
                description=f"CMS status changed: {old_status_label} → {new_status_label}",
                user=request.user,
            )

        match.refresh_from_db()

        detail_context = build_match_detail_side_context(match)
        detail_context["match"] = match
        detail_context["match_status"] = Match.Status

        activity_context = get_match_activity_page_context(match, page=1)
        detail_context.update(activity_context)

        progress_html = render_to_string(
            "operations/partials/match_progress_summary.html",
            detail_context,
            request=request,
        )

        status_html = render_to_string(
            "operations/partials/match_status_badge.html",
            detail_context,
            request=request,
        )

        activity_html = render_to_string(
            "operations/partials/activity_log_timeline.html",
            detail_context,
            request=request,
        )

        response_html = progress_html + status_html + activity_html

        if request.headers.get("HX-Request") == "true":
            return HttpResponse(response_html)

        messages.success(request, "CMS status updated successfully.")
        return redirect("operations:match-detail", pk=match.pk)


