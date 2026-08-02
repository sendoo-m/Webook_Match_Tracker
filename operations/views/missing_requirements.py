
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.utils import timezone
from django.views.generic import TemplateView

from checklists.models import MatchChecklistItem
from matches.models import Match
from matches.utils import combine_match_datetime
from operations.mixins import MatchScopedQuerysetMixin

class MissingRequirementsReportView(LoginRequiredMixin, MatchScopedQuerysetMixin, TemplateView):
    template_name = "operations/reports/missing_requirements.html"
    partial_template_name = "operations/reports/partials/missing_requirements_results.html"

    EXCLUDED_CATEGORY_NAMES = {"Post Match"}
    EXCLUDED_ITEM_TITLES = {"Result", "Report", "Final Result", "Match Report"}
    PAGE_SIZE = 10

    def get_template_names(self):
        if self.request.headers.get("HX-Request") == "true":
            return [self.partial_template_name]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.localtime()
        selected_filter = self.request.GET.get("filter", "all")

        matches = self.filter_matches_queryset(
            Match.objects.select_related("venue", "home_club", "away_club")
            .order_by("event_date", "match_start_time")
            .prefetch_related(
                "checklist_items__template_item__category",
                "checklist_items__completed_by",
            )
        )

        all_rows = []
        for match in matches:
            match_dt = combine_match_datetime(match)
            pending_items_qs = (
                match.checklist_items.select_related("template_item__category", "completed_by")
                .filter(is_active=True)
                .exclude(status=MatchChecklistItem.Status.DONE)
                .exclude(template_item__category__name__in=self.EXCLUDED_CATEGORY_NAMES)
                .exclude(template_item__title__in=self.EXCLUDED_ITEM_TITLES)
                .order_by("template_item__category__sort_order", "template_item__sort_order", "id")
            )
            pending_items = list(pending_items_qs)
            if not pending_items:
                continue
            has_notes = any((item.note or "").strip() for item in pending_items)
            has_delayed = any(item.status == MatchChecklistItem.Status.DELAYED for item in pending_items)
            is_upcoming = bool(match_dt and timezone.localtime(match_dt) >= now)
            all_rows.append({
                "match": match,
                "event_dt": match_dt,
                "pending_count": len(pending_items),
                "pending_items": pending_items,
                "has_notes": has_notes,
                "has_delayed": has_delayed,
                "is_upcoming": is_upcoming,
            })

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
            "report_title": "Missing Operational Requirements",
            "report_subtitle": "All matches with pending items except result and report tasks.",
        })
        return context


# from operations.mixins import MatchScopedQuerysetMixin
# from django.contrib.auth.mixins import LoginRequiredMixin
# from django.core.paginator import Paginator
# from django.utils import timezone
# from django.views.generic import TemplateView


# from checklists.models import MatchChecklistItem
# from matches.models import Match
# from matches.utils import combine_match_datetime
# from operations.mixins import MatchScopedQuerysetMixin


# class MissingRequirementsReportView(LoginRequiredMixin, TemplateView):
#     template_name = "operations/reports/missing_requirements.html"
#     partial_template_name = "operations/reports/partials/missing_requirements_results.html"

#     EXCLUDED_CATEGORY_NAMES = {"Post Match"}
#     EXCLUDED_ITEM_TITLES = {"Result", "Report", "Final Result", "Match Report"}
#     PAGE_SIZE = 10

#     def get_template_names(self):
#         if self.request.headers.get("HX-Request") == "true":
#             return [self.partial_template_name]
#         return [self.template_name]

#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)

#         now = timezone.localtime()
#         selected_filter = self.request.GET.get("filter", "all")

#         matches = (
#             Match.objects.select_related("venue", "home_club", "away_club")
#             .order_by("event_date", "match_start_time")
#             .prefetch_related(
#                 "checklist_items__template_item__category",
#                 "checklist_items__completed_by",
#             )
#         )

#         all_rows = []

#         for match in matches:
#             match_dt = combine_match_datetime(match)

#             pending_items_qs = (
#                 match.checklist_items.select_related(
#                     "template_item__category",
#                     "completed_by",
#                 )
#                 .filter(is_active=True)
#                 .exclude(status=MatchChecklistItem.Status.DONE)
#                 .exclude(template_item__category__name__in=self.EXCLUDED_CATEGORY_NAMES)
#                 .exclude(template_item__title__in=self.EXCLUDED_ITEM_TITLES)
#                 .order_by(
#                     "template_item__category__sort_order",
#                     "template_item__sort_order",
#                     "id",
#                 )
#             )

#             pending_items = list(pending_items_qs)
#             if not pending_items:
#                 continue

#             has_notes = any((item.note or "").strip() for item in pending_items)
#             has_delayed = any(item.status == MatchChecklistItem.Status.DELAYED for item in pending_items)
#             is_upcoming = bool(match_dt and timezone.localtime(match_dt) >= now)

#             all_rows.append({
#                 "match": match,
#                 "event_dt": match_dt,
#                 "pending_count": len(pending_items),
#                 "pending_items": pending_items,
#                 "has_notes": has_notes,
#                 "has_delayed": has_delayed,
#                 "is_upcoming": is_upcoming,
#             })

#         filter_counts = {
#             "all": len(all_rows),
#             "upcoming": sum(1 for row in all_rows if row["is_upcoming"]),
#             "delayed": sum(1 for row in all_rows if row["has_delayed"]),
#             "has_notes": sum(1 for row in all_rows if row["has_notes"]),
#         }

#         if selected_filter == "upcoming":
#             filtered_rows = [row for row in all_rows if row["is_upcoming"]]
#         elif selected_filter == "delayed":
#             filtered_rows = [row for row in all_rows if row["has_delayed"]]
#         elif selected_filter == "has_notes":
#             filtered_rows = [row for row in all_rows if row["has_notes"]]
#         else:
#             filtered_rows = all_rows

#         page_number = self.request.GET.get("page", 1)
#         paginator = Paginator(filtered_rows, self.PAGE_SIZE)
#         page_obj = paginator.get_page(page_number)

#         context.update({
#             "report_rows": page_obj.object_list,
#             "page_obj": page_obj,
#             "paginator": paginator,
#             "selected_filter": selected_filter,
#             "filter_counts": filter_counts,
#             "report_title": "Missing Operational Requirements",
#             "report_subtitle": "All matches with pending items except result and report tasks.",
#         })
#         return context
  