
from datetime import date

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.views.generic import ListView

from checklists.models import MatchChecklistItem
from matches.models import Competition, Match
from operations.permissions import ExcludeClubManagerAccessMixin, MatchScopedQuerysetMixin

from .helpers import get_selectable_clubs


class MatchListView(LoginRequiredMixin, ExcludeClubManagerAccessMixin, MatchScopedQuerysetMixin, ListView):
    model = Match
    template_name = "operations/match_list.html"
    context_object_name = "matches"
    paginate_by = 25

    def get_queryset(self):
        qs = (
            Match.objects.select_related("home_club", "away_club", "venue", "sent_to_cms_by", "competition")
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
            )
        )
        qs = self.filter_matches_queryset(qs)
        status = self.request.GET.get("status")
        club = self.request.GET.get("club")
        competition = self.request.GET.get("competition")
        round_number = self.request.GET.get("round")
        period = self.request.GET.get("period", "upcoming")
        if status:
            qs = qs.filter(cms_status=status)
        if club:
            qs = qs.filter(Q(home_club_id=club) | Q(away_club_id=club))
        if competition:
            qs = qs.filter(competition_id=competition)
        if round_number:
            qs = qs.filter(round_number=round_number)

        today = date.today()
        if period == "past":
            # Matches whose day has already ended - most recent first.
            qs = qs.filter(event_date__lt=today).order_by("-event_date", "-match_start_time", "-id")
        else:
            # Default view: hide matches that are already over. Matches with
            # no date yet (still being set up) stay visible so they aren't lost.
            qs = qs.filter(Q(event_date__gte=today) | Q(event_date__isnull=True))
            qs = qs.order_by("event_date", "match_start_time", "id")
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        allowed_matches = self.filter_matches_queryset(Match.objects.all())
        allowed_competition_ids = allowed_matches.values_list("competition_id", flat=True).distinct()
        context["clubs"] = get_selectable_clubs(allowed_matches)
        context["competitions"] = Competition.objects.filter(
            is_active=True, id__in=allowed_competition_ids
        ).order_by("sort_order", "name_ar")
        context["status_choices"] = Match.Status.choices
        context["available_rounds"] = range(1, 35)
        context["selected_status"] = self.request.GET.get("status", "")
        context["selected_club"] = self.request.GET.get("club", "")
        context["selected_competition"] = self.request.GET.get("competition", "")
        context["selected_round"] = self.request.GET.get("round", "")
        context["selected_period"] = self.request.GET.get("period", "upcoming")
        context["today"] = date.today()
        return context
