
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.views.generic import ListView

from checklists.models import MatchChecklistItem
from matches.models import Club, Competition, Match
from operations.permissions import MatchScopedQuerysetMixin


class MatchListView(LoginRequiredMixin, MatchScopedQuerysetMixin, ListView):
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
        qs = self.filter_matches_queryset(qs)
        status = self.request.GET.get("status")
        club = self.request.GET.get("club")
        competition = self.request.GET.get("competition")
        if status:
            qs = qs.filter(cms_status=status)
        if club:
            qs = qs.filter(Q(home_club__id=club) | Q(away_club__id=club))
        if competition:
            qs = qs.filter(competition_id=competition)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        allowed_matches = self.filter_matches_queryset(Match.objects.all())
        allowed_club_ids = Club.objects.filter(
            Q(home_matches__in=allowed_matches) | Q(away_matches__in=allowed_matches)
        ).distinct().values_list("id", flat=True)
        allowed_competition_ids = allowed_matches.values_list("competition_id", flat=True).distinct()
        context["clubs"] = Club.objects.filter(is_active=True, id__in=allowed_club_ids).order_by("name_ar")
        context["competitions"] = Competition.objects.filter(
            is_active=True, id__in=allowed_competition_ids
        ).order_by("sort_order", "name_ar")
        context["status_choices"] = Match.Status.choices
        context["selected_status"] = self.request.GET.get("status", "")
        context["selected_club"] = self.request.GET.get("club", "")
        context["selected_competition"] = self.request.GET.get("competition", "")
        return context
