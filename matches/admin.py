from django.contrib import admin, messages
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

from checklists.models import MatchChecklistItem, CMSSubmission
from .calendar_sync import CalendarSyncError, sync_roshan_league_from_calendar
from .import_export import (
    build_import_template_xlsx,
    export_calendar_import_xlsx,
    export_matches_csv,
    export_matches_xlsx,
    import_matches_file,
)
from .models import AudienceTier, Club, MapPlacement, Venue, VenueGate, VenueImage, VenueSeatingCategory, Match, Competition

# Where the "Update Roshan League Schedule" button also saves a copy of the
# imported rows as an .xlsx, per the calendar-import feature's requirements.
CALENDAR_EXPORT_SAVE_PATH = r"D:\2025\webook-match-tracker\config\SPL_2026-27_Rounds_6-12_from_calendar.xlsx"


@admin.register(Competition)
class CompetitionAdmin(admin.ModelAdmin):
    list_display = ("name_ar", "name_en", "sort_order", "is_active")
    search_fields = ("name_ar", "name_en")
    list_filter = ("is_active",)
    ordering = ("sort_order", "name_ar")


@admin.register(Club)
class ClubAdmin(admin.ModelAdmin):
    list_display = ("name_ar", "name_en", "short_name", "owner", "is_active")
    search_fields = ("name_ar", "name_en", "short_name", "owner__username")
    list_filter = ("is_active", "owner")
    ordering = ("name_ar",)
    autocomplete_fields = ("owner",)


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ("name_ar", "name_en", "city", "seat_type", "is_active")
    search_fields = ("name_ar", "name_en", "city")
    list_filter = ("is_active", "seat_type", "city")
    ordering = ("name_ar",)


@admin.register(VenueImage)
class VenueImageAdmin(admin.ModelAdmin):
    """Seating-map/overview images shown to clubs on the pricing-plan page -
    the same images the Control Panel's "Venue Images" screen manages, now
    also reachable here."""

    list_display = ("venue", "caption", "sort_order", "is_active")
    search_fields = ("venue__name_ar", "venue__name_en", "caption")
    list_filter = ("is_active", "venue")
    ordering = ("venue__name_ar", "sort_order")
    autocomplete_fields = ("venue",)


@admin.register(AudienceTier)
class AudienceTierAdmin(admin.ModelAdmin):
    """The popularity/audience classifications (e.g. "Premium", "Standard")
    a category can be tagged with - names and count are entirely up to
    SPL/coordinators, never assumed by this codebase; see AudienceTier's
    own docstring for why."""

    list_display = ("name_ar", "name_en", "color", "sort_order", "is_active")
    search_fields = ("name_ar", "name_en")
    list_filter = ("is_active",)
    ordering = ("sort_order", "name_ar")


@admin.register(VenueSeatingCategory)
class VenueSeatingCategoryAdmin(admin.ModelAdmin):
    """The seating category/ticket-type codes (e.g. "CAT 1") a club prices
    against on the pricing-plan page - where each one is actually drawn on
    a seating-map image now lives on MapPlacement instead (a category can
    have more than one placement), see MapPlacementAdmin below."""

    list_display = ("venue", "club", "code", "seat_count", "color", "audience_tier", "has_position", "is_active")
    search_fields = ("venue__name_ar", "venue__name_en", "club__name_ar", "club__name_en", "code")
    list_filter = ("is_active", "venue", "club", "audience_tier")
    ordering = ("venue__name_ar", "club__name_ar", "sort_order", "code")
    autocomplete_fields = ("venue", "club", "audience_tier")

    @admin.display(boolean=True, description="Positioned on map")
    def has_position(self, obj):
        return obj.has_position


@admin.register(VenueGate)
class VenueGateAdmin(admin.ModelAdmin):
    """Physical entry gates at a venue - optionally scoped to one club's
    fans (e.g. an away-supporters-only entrance) at a shared venue."""

    list_display = ("venue", "name", "club", "color", "sort_order", "is_active")
    search_fields = ("venue__name_ar", "venue__name_en", "name", "club__name_ar", "club__name_en")
    list_filter = ("is_active", "venue")
    ordering = ("venue__name_ar", "sort_order", "name")
    autocomplete_fields = ("venue", "club")


@admin.register(MapPlacement)
class MapPlacementAdmin(admin.ModelAdmin):
    """Where a category (or a bare zone/gate marker) is actually drawn on
    one specific seating-map image - see VenueSeatingCategory/MapPlacement
    docstrings for why this is separate from the category itself. A
    category can have more than one row here (e.g. split across a North
    and a South block)."""

    list_display = ("position_image", "club", "category", "gate", "zone_type", "sort_order", "is_active")
    search_fields = (
        "position_image__venue__name_ar", "position_image__venue__name_en",
        "club__name_ar", "club__name_en", "category__code", "gate__name",
    )
    list_filter = ("is_active", "zone_type", "venue")
    ordering = ("venue__name_ar", "club__name_ar", "sort_order")
    autocomplete_fields = ("venue", "club", "position_image", "category", "gate")


class MatchChecklistItemInline(admin.TabularInline):
    model = MatchChecklistItem
    extra = 0
    autocomplete_fields = ("template_item", "completed_by")
    fields = (
        "template_item",
        "status",
        "note",
        "delay_reason",
        "completed_by",
        "completed_at",
        "is_active",
    )
    readonly_fields = ("completed_at",)
    show_change_link = True


class CMSSubmissionInline(admin.StackedInline):
    model = CMSSubmission
    extra = 0
    can_delete = False
    autocomplete_fields = ("sent_by",)
    fields = (
        "status",
        "sent_at",
        "sent_by",
        "cms_reference",
        "notes",
    )


class HasDelayedItemsFilter(admin.SimpleListFilter):
    title = "Has delayed items"
    parameter_name = "has_delayed_items"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Yes"),
            ("no", "No"),
        )

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(
                checklist_items__status=MatchChecklistItem.Status.DELAYED,
                checklist_items__is_active=True,
            ).distinct()
        if self.value() == "no":
            return queryset.exclude(
                checklist_items__status=MatchChecklistItem.Status.DELAYED,
                checklist_items__is_active=True,
            ).distinct()
        return queryset


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = (
        "title_en",
        "competition",
        "home_club",
        "away_club",
        "event_date",
        "match_start_time",
        "discount_code",
        "cms_status",
        "sent_to_cms_at",
        "sent_to_cms_by",
        "checklist_total",
        "checklist_done",
        "checklist_delayed",
        "completion_rate",
        "created_at",
    )
    search_fields = (
        "title_en",
        "title_ar",
        "slug",
        "discount_code",
        "home_club__name_ar",
        "home_club__name_en",
        "away_club__name_ar",
        "away_club__name_en",
        "venue__name_ar",
        "venue__name_en",
    )
    list_filter = (
        "cms_status",
        "competition",
        "event_date",
        "home_club",
        "away_club",
        "venue",
        HasDelayedItemsFilter,
    )
    autocomplete_fields = ("competition", "home_club", "away_club", "venue", "sent_to_cms_by")
    ordering = ("event_date", "match_start_time", "id")
    inlines = [CMSSubmissionInline, MatchChecklistItemInline]
    change_list_template = "admin/matches/match/change_list.html"
    actions = ["export_selected_as_csv", "export_selected_as_xlsx"]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("competition", "home_club", "away_club", "venue", "sent_to_cms_by")
        )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "ops-dashboard/",
                self.admin_site.admin_view(self.ops_dashboard_view),
                name="matches_match_ops_dashboard",
            ),
            path(
                "export/",
                self.admin_site.admin_view(self.export_all_view),
                name="matches_match_export",
            ),
            path(
                "import/",
                self.admin_site.admin_view(self.import_view),
                name="matches_match_import",
            ),
            path(
                "template/",
                self.admin_site.admin_view(self.template_view),
                name="matches_match_template",
            ),
            path(
                "sync-calendar/",
                self.admin_site.admin_view(self.sync_calendar_view),
                name="matches_match_sync_calendar",
            ),
            path(
                "export-calendar/",
                self.admin_site.admin_view(self.export_calendar_view),
                name="matches_match_export_calendar",
            ),
        ]
        return custom_urls + urls

    @admin.action(description="Export selected matches as CSV")
    def export_selected_as_csv(self, request, queryset):
        csv_content = export_matches_csv(queryset)
        response = HttpResponse(csv_content, content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="matches_export.csv"'
        return response

    @admin.action(description="Export selected matches as Excel (.xlsx)")
    def export_selected_as_xlsx(self, request, queryset):
        xlsx_content = export_matches_xlsx(queryset)
        response = HttpResponse(
            xlsx_content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="matches_export.xlsx"'
        return response

    def export_all_view(self, request):
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

    def template_view(self, request):
        content = build_import_template_xlsx()
        response = HttpResponse(
            content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="matches_import_template.xlsx"'
        return response

    def import_view(self, request):
        if request.method != "POST":
            context = {
                **self.admin_site.each_context(request),
                "opts": self.model._meta,
                "title": "Import matches",
                "competitions": Competition.objects.filter(is_active=True).order_by("sort_order", "name_ar"),
            }
            return TemplateResponse(request, "admin/matches/match/import_confirm.html", context)

        import_file = request.FILES.get("import_file")
        if not import_file:
            self.message_user(request, "Please choose a CSV or Excel file.", level=messages.ERROR)
            return redirect(reverse("admin:matches_match_import"))

        competition_id = request.POST.get("competition") or None
        result = import_matches_file(import_file, import_file.name, competition_id and int(competition_id))
        if result.errors:
            self.message_user(
                request,
                f"Import completed with errors. Created: {result.created}, updated: {result.updated}, "
                f"skipped: {len(result.skipped)}, errors: {len(result.errors)} "
                f"(first: row {result.errors[0][0]} - {result.errors[0][1]}).",
                level=messages.WARNING,
            )
        else:
            self.message_user(
                request,
                f"Import completed successfully. Created: {result.created}, updated: {result.updated}, "
                f"skipped: {len(result.skipped)}.",
                level=messages.SUCCESS,
            )
        return redirect(reverse("admin:matches_match_changelist"))

    def sync_calendar_view(self, request):
        """"Update Roshan League Schedule" button: GET shows a confirm page,
        POST runs matches.calendar_sync.sync_roshan_league_from_calendar()
        against the live database (Matchweeks 6-12 only) and also saves a
        copy of the imported rows to CALENDAR_EXPORT_SAVE_PATH."""
        if request.method != "POST":
            context = {
                **self.admin_site.each_context(request),
                "opts": self.model._meta,
                "title": "Update Roshan League Schedule",
            }
            return TemplateResponse(request, "admin/matches/match/calendar_sync_confirm.html", context)

        try:
            result = sync_roshan_league_from_calendar()
        except CalendarSyncError as exc:
            self.message_user(request, f"Calendar sync failed: {exc}", level=messages.ERROR)
            return redirect(reverse("admin:matches_match_changelist"))

        saved_note = ""
        try:
            xlsx_content = export_calendar_import_xlsx(result.rows)
            with open(CALENDAR_EXPORT_SAVE_PATH, "wb") as xlsx_file:
                xlsx_file.write(xlsx_content)
            saved_note = f" A copy was saved to {CALENDAR_EXPORT_SAVE_PATH}."
        except OSError as exc:
            saved_note = f" (Could not save the Excel copy: {exc})"

        skip_note = ""
        if result.skipped:
            first_reasons = "; ".join(f"{summary} - {reason}" for summary, reason in result.skipped[:5])
            skip_note = f" Skipped {len(result.skipped)}: {first_reasons}."
            if len(result.skipped) > 5:
                skip_note += f" (+{len(result.skipped) - 5} more)"

        self.message_user(
            request,
            f"Calendar sync completed. Created: {result.created}, updated: {result.updated}, "
            f"ignored (unparsed round): {result.ignored_out_of_range}.{skip_note}{saved_note}",
            level=messages.WARNING if result.skipped else messages.SUCCESS,
        )
        return redirect(reverse("admin:matches_match_changelist"))

    def export_calendar_view(self, request):
        """"Export Calendar Import (Excel)" button: single-click, dry-run
        fetch (no database writes) that streams the same rows the sync
        button would create/update as an .xlsx download."""
        try:
            result = sync_roshan_league_from_calendar(dry_run=True)
        except CalendarSyncError as exc:
            self.message_user(request, f"Could not export from the calendar: {exc}", level=messages.ERROR)
            return redirect(reverse("admin:matches_match_changelist"))

        content = export_calendar_import_xlsx(result.rows)
        response = HttpResponse(
            content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="SPL_2026-27_Rounds_6-12_from_calendar.xlsx"'
        return response

    def ops_dashboard_view(self, request):
        matches = Match.objects.all()

        stats = {
            "total_matches": matches.count(),
            "draft_matches": matches.filter(cms_status=Match.Status.DRAFT).count(),
            "in_progress_matches": matches.filter(cms_status=Match.Status.IN_PROGRESS).count(),
            "ready_for_cms_matches": matches.filter(cms_status=Match.Status.READY_FOR_CMS).count(),
            "sent_to_cms_matches": matches.filter(cms_status=Match.Status.SENT_TO_CMS).count(),
            "published_matches": matches.filter(cms_status=Match.Status.PUBLISHED).count(),
            "delayed_matches": matches.filter(
                checklist_items__status=MatchChecklistItem.Status.DELAYED,
                checklist_items__is_active=True,
            ).distinct().count(),
        }

        upcoming_matches = (
            Match.objects.select_related("home_club", "away_club", "venue")
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
            .order_by("event_date", "match_start_time")[:10]
        )

        context = {
            **self.admin_site.each_context(request),
            "title": "Operations Dashboard",
            "stats": stats,
            "upcoming_matches": upcoming_matches,
        }
        return TemplateResponse(request, "admin/ops_dashboard.html", context)

    @admin.display(description="Checklist Total")
    def checklist_total(self, obj):
        return obj.checklist_items.filter(is_active=True).count()

    @admin.display(description="Done")
    def checklist_done(self, obj):
        return obj.checklist_items.filter(
            status=MatchChecklistItem.Status.DONE,
            is_active=True,
        ).count()

    @admin.display(description="Delayed")
    def checklist_delayed(self, obj):
        return obj.checklist_items.filter(
            status=MatchChecklistItem.Status.DELAYED,
            is_active=True,
        ).count()

    @admin.display(description="Completion")
    def completion_rate(self, obj):
        total = obj.checklist_items.filter(is_active=True).count()
        if total == 0:
            return "0%"
        done = obj.checklist_items.filter(
            status=MatchChecklistItem.Status.DONE,
            is_active=True,
        ).count()
        return f"{round((done / total) * 100)}%"
