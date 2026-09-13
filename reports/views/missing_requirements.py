# reports/views/missing_requirements.py

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from django.views.generic import TemplateView

from checklists.models import MatchChecklistItem
from matches.models import Competition, Match
from matches.utils import combine_match_datetime
from operations.permissions import (
    ExcludeClubManagerAccessMixin,
    ExcludeViewerAccessMixin,
    MatchScopedQuerysetMixin,
    can_view_all_matches,
)

from operations.views.helpers import (
    get_match_detail_prefetch,
    get_missing_requirements_eligible_items_count,
    get_missing_requirements_pending_items,
    get_selectable_clubs,
    is_kv_ready,
)

class MissingRequirementsReportView(
    LoginRequiredMixin,
    ExcludeViewerAccessMixin,
    ExcludeClubManagerAccessMixin,
    MatchScopedQuerysetMixin,
    TemplateView,
):
    template_name = "operations/reports/missing_requirements.html"
    partial_template_name = "operations/reports/partials/missing_requirements_results.html"

    PAGE_SIZE = 10

    def get_template_names(self):
        if self.request.headers.get("HX-Request") == "true":
            return [self.partial_template_name]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.localtime()
        selected_filter = self.request.GET.get("filter", "all")
        is_admin = can_view_all_matches(self.request.user)

        selected_club = self.request.GET.get("club", "")
        selected_competition = self.request.GET.get("competition", "")
        selected_round = self.request.GET.get("round", "")
        selected_user = self.request.GET.get("user", "") if is_admin else ""
        selected_spl_approval = self.request.GET.get("spl_approval", "")
        selected_kv_status = self.request.GET.get("kv_status", "")

        scoped_matches = self.filter_matches_queryset(Match.objects.all())

        allowed_competition_ids = scoped_matches.values_list("competition_id", flat=True).distinct()

        context["clubs"] = get_selectable_clubs(scoped_matches)
        context["competitions"] = Competition.objects.filter(
            is_active=True, id__in=allowed_competition_ids
        ).order_by("sort_order", "name_ar")
        context["rounds"] = (
            scoped_matches.exclude(round_number__isnull=True)
            .values_list("round_number", flat=True).distinct().order_by("round_number")
        )
        context["is_admin"] = is_admin
        if is_admin:
            User = get_user_model()
            context["users"] = User.objects.filter(owned_clubs__isnull=False).distinct().order_by("username")

        matches = (
            scoped_matches.select_related("venue", "home_club", "away_club")
            .order_by("event_date", "match_start_time")
            .prefetch_related(get_match_detail_prefetch())
        )
        if selected_club:
            matches = matches.filter(Q(home_club_id=selected_club) | Q(away_club_id=selected_club))
        if selected_competition:
            matches = matches.filter(competition_id=selected_competition)
        if selected_round:
            matches = matches.filter(round_number=selected_round)
        if selected_user:
            matches = matches.filter(home_club__owner_id=selected_user)
        if selected_spl_approval == "approved":
            matches = matches.filter(ticketing_plan_approved=True)
        elif selected_spl_approval == "not_approved":
            matches = matches.filter(ticketing_plan_approved=False)

        all_rows = []
        for match in matches:
            match_dt = combine_match_datetime(match)
            pending_items = list(get_missing_requirements_pending_items(match))
            if not pending_items:
                continue
            has_notes = any((item.note or "").strip() for item in pending_items)
            has_delayed = any(item.status == MatchChecklistItem.Status.DELAYED for item in pending_items)
            is_upcoming = bool(match_dt and timezone.localtime(match_dt) >= now)

            categories_by_id = {}
            for item in pending_items:
                category = item.template_item.category
                categories_by_id.setdefault(category.id, category)
            pending_categories = sorted(categories_by_id.values(), key=lambda c: c.sort_order)

            total_items = get_missing_requirements_eligible_items_count(match)
            done_items = total_items - len(pending_items)

            all_rows.append({
                "match": match,
                "event_dt": match_dt,
                "pending_count": len(pending_items),
                "pending_items": pending_items,
                "pending_categories": pending_categories,
                "total_items": total_items,
                "done_items": done_items,
                "has_notes": has_notes,
                "has_delayed": has_delayed,
                "is_upcoming": is_upcoming,
                "kv_ready": is_kv_ready(match),
            })

        if selected_kv_status == "ready":
            all_rows = [row for row in all_rows if row["kv_ready"]]
        elif selected_kv_status == "not_ready":
            all_rows = [row for row in all_rows if not row["kv_ready"]]

        filter_counts = {
            "all": len(all_rows),
            "upcoming": sum(1 for row in all_rows if row["is_upcoming"]),
            "delayed": sum(1 for row in all_rows if row["has_delayed"]),
            "has_notes": sum(1 for row in all_rows if row["has_notes"]),
        }

        if selected_filter == "upcoming":
            filtered_rows = [row for row in all_rows if row["is_upcoming"]]
        elif selected_filter == "delayed":
            filtered_rows = [row for row in all_rows if row["has_delayed"]]
        elif selected_filter == "has_notes":
            filtered_rows = [row for row in all_rows if row["has_notes"]]
        else:
            filtered_rows = all_rows

        paginator = Paginator(filtered_rows, self.PAGE_SIZE)
        page_obj = paginator.get_page(self.request.GET.get("page", 1))

        context.update({
            "report_rows": page_obj.object_list,
            "page_obj": page_obj,
            "paginator": paginator,
            "selected_filter": selected_filter,
            "filter_counts": filter_counts,
            "selected_club": selected_club,
            "selected_competition": selected_competition,
            "selected_round": selected_round,
            "selected_user": selected_user,
            "selected_spl_approval": selected_spl_approval,
            "selected_kv_status": selected_kv_status,
            "report_title": "Missing Operational Requirements",
            "report_subtitle": "All matches with pending items except result and report tasks.",
        })
        return context
