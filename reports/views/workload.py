from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.views.generic import TemplateView

from control_panel.permissions import ControlPanelAccessMixin
from matches.models import Competition, Match
from operations.views.helpers import get_selectable_clubs

User = get_user_model()


class CoordinatorWorkloadReportView(LoginRequiredMixin, ControlPanelAccessMixin, TemplateView):
    template_name = "operations/reports/workload.html"
    PAGE_SIZE = 25

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        selected_user = self.request.GET.get("user", "")
        selected_club = self.request.GET.get("club", "")
        selected_competition = self.request.GET.get("competition", "")
        selected_round = self.request.GET.get("round", "")

        matches = Match.objects.select_related(
            "home_club", "home_club__owner", "away_club", "venue", "competition"
        )
        if selected_user:
            matches = matches.filter(home_club__owner_id=selected_user)
        if selected_club:
            matches = matches.filter(home_club_id=selected_club)
        if selected_competition:
            matches = matches.filter(competition_id=selected_competition)
        if selected_round:
            matches = matches.filter(round_number=selected_round)
        matches = matches.order_by("event_date", "match_start_time", "id")

        remaining_filter = ~Q(cms_status=Match.Status.PUBLISHED)

        by_user = list(
            matches.filter(home_club__owner__isnull=False)
            .values(
                "home_club__owner_id",
                "home_club__owner__username",
                "home_club__owner__first_name",
                "home_club__owner__last_name",
            )
            .annotate(total=Count("id"), remaining=Count("id", filter=remaining_filter))
            .order_by("-remaining", "home_club__owner__username")
        )
        for row in by_user:
            full_name = f"{row['home_club__owner__first_name']} {row['home_club__owner__last_name']}".strip()
            row["coordinator_display_name"] = full_name or row["home_club__owner__username"]
        by_club = list(
            matches.values("home_club_id", "home_club__name_ar")
            .annotate(total=Count("id"), remaining=Count("id", filter=remaining_filter))
            .order_by("-remaining", "home_club__name_ar")
        )
        # Grouped by (competition, round_number), not round_number alone -
        # different competitions number their rounds independently (a King
        # Cup "Round 3" and a Roshan League "Round 3" are unrelated), so
        # grouping by round_number alone would silently merge their totals
        # into one misleading row.
        by_round = list(
            matches.exclude(round_number__isnull=True)
            .values("round_number", "competition_id", "competition__name_ar", "competition__name_en")
            .annotate(total=Count("id"), remaining=Count("id", filter=remaining_filter))
            .order_by("competition__sort_order", "round_number")
        )

        paginator = Paginator(matches, self.PAGE_SIZE)
        page_obj = paginator.get_page(self.request.GET.get("page", 1))

        context.update({
            "matches": page_obj.object_list,
            "page_obj": page_obj,
            "paginator": paginator,
            "total_count": paginator.count,
            "remaining_count": matches.filter(remaining_filter).count(),
            "by_user": by_user,
            "by_club": by_club,
            "by_round": by_round,
            "users": User.objects.filter(owned_clubs__isnull=False).distinct().order_by("username"),
            "clubs": get_selectable_clubs(Match.objects.all()),
            "competitions": Competition.objects.filter(is_active=True).order_by("sort_order", "name_ar"),
            "rounds": Match.objects.exclude(round_number__isnull=True)
                .values_list("round_number", flat=True).distinct().order_by("round_number"),
            "selected_user": selected_user,
            "selected_club": selected_club,
            "selected_competition": selected_competition,
            "selected_round": selected_round,
            "today": date.today(),
        })
        return context
