from datetime import date

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import FormView

from checklists.services import attach_default_checklist_items
from control_panel.forms import MatchExportFilterForm, MatchForm, MatchImportForm
from control_panel.permissions import ControlPanelAccessMixin
from matches.calendar_sync import CalendarSyncError, sync_roshan_league_from_calendar
from matches.import_export import (
    build_import_template_xlsx,
    export_matches_csv,
    export_matches_xlsx,
    import_matches_file,
)
from matches.models import Club, Match, Venue
from operations.permissions import can_access_limited_control_panel, can_manage_control_panel, get_owned_club_ids

from .base import PanelCreateView, PanelListView, PanelUpdateView


class MatchAdminListView(PanelListView):
    """A Club Manager coordinator can also reach this page (see
    can_access_limited_control_panel) - test_func is overridden to admit
    them, and get_queryset/get_context_data narrow everything they see to
    their own clubs' fixtures. "Add Match" stays admin-only (creating a
    fresh fixture is rare/riskier than editing one that already exists),
    so its create_url is dropped from context for a non-admin instead of
    linking to a page that would just 403 them."""

    model = Match
    template_name = "control_panel/match_list.html"
    context_object_name = "matches"
    ordering = ["-event_date", "-match_start_time", "-id"]
    page_title = _("Matches")
    create_url_name = "control_panel:match-create"
    create_label = _("Add Match")

    def test_func(self):
        return can_access_limited_control_panel(self.request.user)

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            "competition", "home_club", "away_club", "venue"
        )
        if not can_manage_control_panel(self.request.user):
            club_ids = get_owned_club_ids(self.request.user)
            queryset = queryset.filter(Q(home_club_id__in=club_ids) | Q(away_club_id__in=club_ids))
        round_number = self.request.GET.get("round", "")
        club_id = self.request.GET.get("club", "")
        city = self.request.GET.get("city", "")
        if round_number:
            queryset = queryset.filter(round_number=round_number)
        if club_id:
            queryset = queryset.filter(Q(home_club_id=club_id) | Q(away_club_id=club_id))
        if city:
            queryset = queryset.filter(venue__city=city)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        is_full_admin = can_manage_control_panel(self.request.user)
        context["export_form"] = MatchExportFilterForm()
        context["selected_round"] = self.request.GET.get("round", "")
        context["selected_club"] = self.request.GET.get("club", "")
        context["selected_city"] = self.request.GET.get("city", "")
        context["rounds"] = (
            Match.objects.exclude(round_number__isnull=True)
            .values_list("round_number", flat=True).distinct().order_by("round_number")
        )
        if is_full_admin:
            context["clubs"] = Club.objects.filter(is_active=True).order_by("name_ar")
        else:
            context["clubs"] = Club.objects.filter(id__in=get_owned_club_ids(self.request.user)).order_by("name_ar")
        context["cities"] = (
            Venue.objects.exclude(city="").values_list("city", flat=True).distinct().order_by("city")
        )
        context["today"] = date.today()
        context["is_full_admin"] = is_full_admin
        if not is_full_admin:
            # No "Add Match" for a coordinator - see class docstring.
            context.pop("create_url", None)
        return context


class MatchAdminCreateView(PanelCreateView):
    model = Match
    form_class = MatchForm
    template_name = "control_panel/match_form.html"
    success_url = reverse_lazy("control_panel:match-list")
    success_message = _("Match created.")
    page_title = _("Add Match")
    list_url_name = "control_panel:match-list"

    def form_valid(self, form):
        response = super().form_valid(form)
        attach_default_checklist_items(self.object)
        return response


class MatchAdminUpdateView(PanelUpdateView):
    """Same scoped access as MatchAdminListView - a coordinator can only
    open/save a match where their own club is home or away; every field on
    the form stays exactly as-is for them, including the SPL/ticketing ones,
    matching Control Panel admin behavior exactly once they're in scope."""

    model = Match
    form_class = MatchForm
    template_name = "control_panel/match_form.html"
    success_url = reverse_lazy("control_panel:match-list")
    success_message = _("Match updated.")
    page_title = _("Edit Match")
    list_url_name = "control_panel:match-list"

    def test_func(self):
        return can_access_limited_control_panel(self.request.user)

    def get_queryset(self):
        queryset = super().get_queryset()
        if not can_manage_control_panel(self.request.user):
            club_ids = get_owned_club_ids(self.request.user)
            queryset = queryset.filter(Q(home_club_id__in=club_ids) | Q(away_club_id__in=club_ids))
        return queryset

    def get_success_url(self):
        if not can_manage_control_panel(self.request.user):
            return reverse("control_panel:venue-control") + "?tab=matches"
        return str(self.success_url)


class MatchExportView(LoginRequiredMixin, ControlPanelAccessMixin, View):
    def get(self, request, *args, **kwargs):
        queryset = Match.objects.all()
        competition_id = request.GET.get("competition")
        if competition_id:
            queryset = queryset.filter(competition_id=competition_id)

        if request.GET.get("format") == "csv":
            content = export_matches_csv(queryset)
            response = HttpResponse(content, content_type="text/csv; charset=utf-8")
            response["Content-Disposition"] = 'attachment; filename="matches_export.csv"'
        else:
            content = export_matches_xlsx(queryset)
            response = HttpResponse(
                content,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = 'attachment; filename="matches_export.xlsx"'
        return response


class MatchTemplateView(LoginRequiredMixin, ControlPanelAccessMixin, View):
    def get(self, request, *args, **kwargs):
        content = build_import_template_xlsx()
        response = HttpResponse(
            content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="matches_import_template.xlsx"'
        return response


class MatchImportView(LoginRequiredMixin, ControlPanelAccessMixin, FormView):
    template_name = "control_panel/match_import.html"
    form_class = MatchImportForm

    def get_success_url(self):
        return reverse("control_panel:match-import")

    def form_valid(self, form):
        import_file = form.cleaned_data["import_file"]
        competition = form.cleaned_data.get("competition")
        result = import_matches_file(
            import_file, import_file.name, competition.id if competition else None
        )
        return self.render_to_response(self.get_context_data(form=self.form_class(), result=result))


class MatchSyncCalendarView(LoginRequiredMixin, ControlPanelAccessMixin, View):
    """"Update Roshan League Schedule" button on the Control Panel's Matches
    page - the same matches.calendar_sync.sync_roshan_league_from_calendar()
    used by the Django Admin button and the sync_roshan_calendar management
    command, just surfaced here too. GET shows a confirm page; POST runs the
    sync (every round, not just 6-12) and redirects back to the match list
    with a result message."""

    def get(self, request, *args, **kwargs):
        return TemplateResponse(request, "control_panel/match_sync_calendar.html", {})

    def post(self, request, *args, **kwargs):
        try:
            result = sync_roshan_league_from_calendar()
        except CalendarSyncError as exc:
            messages.error(request, _("Calendar sync failed: %(error)s") % {"error": exc})
            return redirect("control_panel:match-list")

        skip_note = ""
        if result.skipped:
            skip_note = _(" %(count)s fixture(s) skipped (unrecognized club or kickoff time not yet confirmed).") % {
                "count": len(result.skipped)
            }

        messages.success(
            request,
            _("Calendar sync completed. Created: %(created)s, updated: %(updated)s.%(skip_note)s") % {
                "created": result.created,
                "updated": result.updated,
                "skip_note": skip_note,
            },
        )
        return redirect("control_panel:match-list")
