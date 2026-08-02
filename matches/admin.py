from django.contrib import admin
from django.db.models import Count, Q
from django.template.response import TemplateResponse
from django.urls import path

from checklists.models import MatchChecklistItem, CMSSubmission
from .models import Club, Venue, Match


# @admin.register(Club)
# class ClubAdmin(admin.ModelAdmin):
#     list_display = ("name_ar", "name_en", "short_name", "is_active")
#     search_fields = ("name_ar", "name_en", "short_name")
#     list_filter = ("is_active",)
#     ordering = ("name_ar",)
@admin.register(Club)
class ClubAdmin(admin.ModelAdmin):
    list_display = ("name_ar", "name_en", "short_name", "owner", "is_active")
    search_fields = ("name_ar", "name_en", "short_name", "owner__username")
    list_filter = ("is_active", "owner")
    ordering = ("name_ar",)
    autocomplete_fields = ("owner",)


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ("name_ar", "name_en", "city", "is_active")
    search_fields = ("name_ar", "name_en", "city")
    list_filter = ("is_active", "city")
    ordering = ("name_ar",)


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
        "home_club",
        "away_club",
        "event_date",
        "match_start_time",
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
        "home_club__name_ar",
        "home_club__name_en",
        "away_club__name_ar",
        "away_club__name_en",
        "venue__name_ar",
        "venue__name_en",
    )
    list_filter = (
        "cms_status",
        "event_date",
        "home_club",
        "away_club",
        "venue",
        HasDelayedItemsFilter,
    )
    autocomplete_fields = ("home_club", "away_club", "venue", "sent_to_cms_by")
    ordering = ("event_date", "match_start_time", "id")
    inlines = [CMSSubmissionInline, MatchChecklistItemInline]
    change_list_template = "admin/matches/match/change_list.html"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("home_club", "away_club", "venue", "sent_to_cms_by")
        )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "ops-dashboard/",
                self.admin_site.admin_view(self.ops_dashboard_view),
                name="matches_match_ops_dashboard",
            ),
        ]
        return custom_urls + urls

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
    
# from django.contrib import admin
# from django.db.models import Count, Q
# from django.template.response import TemplateResponse
# from django.urls import path

# from checklists.models import MatchChecklistItem, CMSSubmission
# from .models import Club, Venue, Match


# @admin.register(Club)
# class ClubAdmin(admin.ModelAdmin):
#     list_display = ("name_ar", "name_en", "is_active", "created_at")
#     search_fields = ("name_ar", "name_en", "short_name_ar", "short_name_en")
#     list_filter = ("is_active",)
#     ordering = ("name_ar",)


# @admin.register(Venue)
# class VenueAdmin(admin.ModelAdmin):
#     list_display = ("name_ar", "name_en", "city_ar", "is_active", "created_at")
#     search_fields = ("name_ar", "name_en", "city_ar", "city_en")
#     list_filter = ("is_active", "city_ar")
#     ordering = ("name_ar",)


# class MatchChecklistItemInline(admin.TabularInline):
#     model = MatchChecklistItem
#     extra = 0
#     autocomplete_fields = ("template_item", "completed_by")
#     fields = (
#         "template_item",
#         "status",
#         "note",
#         "delay_reason",
#         "completed_by",
#         "completed_at",
#     )
#     readonly_fields = ("completed_at",)
#     show_change_link = True


# class CMSSubmissionInline(admin.StackedInline):
#     model = CMSSubmission
#     extra = 0
#     can_delete = False
#     autocomplete_fields = ("sent_by",)
#     fields = (
#         "status",
#         "sent_at",
#         "sent_by",
#         "cms_reference",
#         "notes",
#     )


# class HasDelayedItemsFilter(admin.SimpleListFilter):
#     title = "Has delayed items"
#     parameter_name = "has_delayed_items"

#     def lookups(self, request, model_admin):
#         return (
#             ("yes", "Yes"),
#             ("no", "No"),
#         )

#     def queryset(self, request, queryset):
#         if self.value() == "yes":
#             return queryset.filter(
#                 checklist_items__status=MatchChecklistItem.Status.DELAYED
#             ).distinct()
#         if self.value() == "no":
#             return queryset.exclude(
#                 checklist_items__status=MatchChecklistItem.Status.DELAYED
#             ).distinct()
#         return queryset


# @admin.register(Match)
# class MatchAdmin(admin.ModelAdmin):
#     list_display = (
#         "title_en",
#         "home_club",
#         "away_club",
#         "event_date",
#         "match_start_time",
#         "cms_status",
#         "checklist_total",
#         "checklist_done",
#         "checklist_delayed",
#         "completion_rate",
#         "created_at",
#     )
#     search_fields = (
#         "title_en",
#         "title_ar",
#         "slug",
#         "home_club__name_ar",
#         "home_club__name_en",
#         "away_club__name_ar",
#         "away_club__name_en",
#         "venue__name_ar",
#         "venue__name_en",
#     )
#     list_filter = (
#         "cms_status",
#         "event_date",
#         "home_club",
#         "away_club",
#         "venue",
#         HasDelayedItemsFilter,
#     )
#     autocomplete_fields = ("home_club", "away_club", "venue")
#     ordering = ("event_date", "match_start_time", "id")
#     inlines = [CMSSubmissionInline, MatchChecklistItemInline]
#     change_list_template = "admin/matches/match/change_list.html"

#     def get_urls(self):
#         urls = super().get_urls()
#         custom_urls = [
#             path(
#                 "ops-dashboard/",
#                 self.admin_site.admin_view(self.ops_dashboard_view),
#                 name="matches_match_ops_dashboard",
#             ),
#         ]
#         return custom_urls + urls

#     def ops_dashboard_view(self, request):
#         matches = Match.objects.all()

#         stats = {
#             "total_matches": matches.count(),
#             "draft_matches": matches.filter(cms_status=Match.Status.DRAFT).count(),
#             "in_progress_matches": matches.filter(cms_status=Match.Status.IN_PROGRESS).count(),
#             "ready_for_cms_matches": matches.filter(cms_status=Match.Status.READY_FOR_CMS).count(),
#             "sent_to_cms_matches": matches.filter(cms_status=Match.Status.SENT_TO_CMS).count(),
#             "published_matches": matches.filter(cms_status=Match.Status.PUBLISHED).count(),
#             "delayed_matches": matches.filter(
#                 checklist_items__status=MatchChecklistItem.Status.DELAYED
#             ).distinct().count(),
#         }

#         upcoming_matches = (
#             Match.objects.select_related("home_club", "away_club", "venue")
#             .annotate(
#                 total_items=Count("checklist_items"),
#                 done_items=Count(
#                     "checklist_items",
#                     filter=Q(checklist_items__status=MatchChecklistItem.Status.DONE),
#                 ),
#                 delayed_items=Count(
#                     "checklist_items",
#                     filter=Q(checklist_items__status=MatchChecklistItem.Status.DELAYED),
#                 ),
#             )
#             .order_by("event_date", "match_start_time")[:10]
#         )

#         context = {
#             **self.admin_site.each_context(request),
#             "title": "Operations Dashboard",
#             "stats": stats,
#             "upcoming_matches": upcoming_matches,
#         }
#         return TemplateResponse(request, "admin/ops_dashboard.html", context)

#     def checklist_total(self, obj):
#         return obj.checklist_items.count()
#     checklist_total.short_description = "Checklist Total"

#     def checklist_done(self, obj):
#         return obj.checklist_items.filter(
#             status=MatchChecklistItem.Status.DONE
#         ).count()
#     checklist_done.short_description = "Done"

#     def checklist_delayed(self, obj):
#         return obj.checklist_items.filter(
#             status=MatchChecklistItem.Status.DELAYED
#         ).count()
#     checklist_delayed.short_description = "Delayed"

#     def completion_rate(self, obj):
#         total = obj.checklist_items.count()
#         if total == 0:
#             return "0%"
#         done = obj.checklist_items.filter(
#             status=MatchChecklistItem.Status.DONE
#         ).count()
#         return f"{round((done / total) * 100)}%"
#     completion_rate.short_description = "Completion"