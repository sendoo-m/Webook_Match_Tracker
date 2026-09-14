# control_panel/views/venue_details.py
#
# Venue-level seating reference data (images + category codes) - shared
# by every club that plays at a venue, not tied to any one club. Managed
# here by coordinators/admin; consumed read-only on the club-facing
# pricing-plan page (Phase 3 of the venue-seating/pricing plan).

from itertools import groupby

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import FormView

from control_panel.forms import VenueCategoryImportForm, VenueImageForm, VenueSeatingCategoryForm
from control_panel.permissions import ControlPanelAccessMixin
from matches.models import Club, VenueImage, VenueSeatingCategory
from matches.venue_category_import_export import (
    build_venue_category_import_template_xlsx,
    export_venue_categories_xlsx,
    import_venue_categories_xlsx,
)

User = get_user_model()

from .base import PanelCreateView, PanelListView, PanelToggleActiveView, PanelUpdateView


class VenueImageListView(PanelListView):
    model = VenueImage
    template_name = "control_panel/venueimage_list.html"
    context_object_name = "venue_images"
    ordering = ["venue__name_ar", "sort_order"]
    page_title = _("Venue Images")
    create_url_name = "control_panel:venue-image-create"
    create_label = _("Add Venue Image")

    def get_queryset(self):
        return super().get_queryset().select_related("venue")


class VenueImageCreateView(PanelCreateView):
    model = VenueImage
    form_class = VenueImageForm
    template_name = "control_panel/venueimage_form.html"
    success_url = reverse_lazy("control_panel:venue-image-list")
    success_message = _("Venue image created.")
    page_title = _("Add Venue Image")
    list_url_name = "control_panel:venue-image-list"


class VenueImageUpdateView(PanelUpdateView):
    model = VenueImage
    form_class = VenueImageForm
    template_name = "control_panel/venueimage_form.html"
    success_url = reverse_lazy("control_panel:venue-image-list")
    success_message = _("Venue image updated.")
    page_title = _("Edit Venue Image")
    list_url_name = "control_panel:venue-image-list"


class VenueImageToggleActiveView(PanelToggleActiveView):
    model = VenueImage
    success_url_name = "control_panel:venue-image-list"


class VenueSeatingCategoryListView(PanelListView):
    """Grouped by club rather than one flat table - with 18 clubs and up to
    ~200 categories for a single club, a flat paginated list makes it hard
    to find anything. Ordering by club first (not venue first, as before)
    is what makes the groupby() in get_context_data valid - groupby only
    groups consecutive items, so the queryset's own ordering has to match
    the grouping key."""

    model = VenueSeatingCategory
    template_name = "control_panel/venueseatingcategory_list.html"
    context_object_name = "categories"
    ordering = ["club__name_ar", "sort_order", "code"]
    page_title = _("Venue Seating Categories")
    create_url_name = "control_panel:venue-category-create"
    create_label = _("Add Category")
    paginate_by = None

    def get_queryset(self):
        queryset = super().get_queryset().select_related("venue", "club")

        club = self.request.GET.get("club", "").strip()
        if club:
            queryset = queryset.filter(club_id=club)

        coordinator = self.request.GET.get("coordinator", "").strip()
        if coordinator:
            queryset = queryset.filter(club__owner_id=coordinator)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        categories = context[self.context_object_name]
        context["grouped_categories"] = [
            {"club": club, "categories": list(group)}
            for club, group in groupby(categories, key=lambda category: category.club)
        ]
        context["club_choices"] = Club.objects.filter(is_active=True).order_by("name_ar")
        context["coordinator_choices"] = User.objects.filter(
            owned_clubs__isnull=False, is_active=True
        ).distinct().order_by("username")
        context["selected_club"] = self.request.GET.get("club", "")
        context["selected_coordinator"] = self.request.GET.get("coordinator", "")
        context["has_active_filters"] = any([context["selected_club"], context["selected_coordinator"]])
        return context


class VenueSeatingCategoryCreateView(PanelCreateView):
    model = VenueSeatingCategory
    form_class = VenueSeatingCategoryForm
    template_name = "control_panel/venueseatingcategory_form.html"
    success_url = reverse_lazy("control_panel:venue-category-list")
    success_message = _("Venue seating category created.")
    page_title = _("Add Venue Seating Category")
    list_url_name = "control_panel:venue-category-list"


class VenueSeatingCategoryUpdateView(PanelUpdateView):
    model = VenueSeatingCategory
    form_class = VenueSeatingCategoryForm
    template_name = "control_panel/venueseatingcategory_form.html"
    success_url = reverse_lazy("control_panel:venue-category-list")
    success_message = _("Venue seating category updated.")
    page_title = _("Edit Venue Seating Category")
    list_url_name = "control_panel:venue-category-list"


class VenueSeatingCategoryToggleActiveView(PanelToggleActiveView):
    model = VenueSeatingCategory
    success_url_name = "control_panel:venue-category-list"


class VenueCategoryTemplateView(LoginRequiredMixin, ControlPanelAccessMixin, View):
    """Downloads a template pre-filled with the chosen venue/club's
    existing category codes (or just the header row if it has none yet) -
    venue and club are picked via GET params from the same select inputs
    shown on the import page."""

    def get(self, request, *args, **kwargs):
        form = VenueCategoryImportForm(data=request.GET)
        # Only venue/club are relevant here - drop import_file from
        # required-field validation by checking those two fields alone.
        venue = form.fields["venue"].queryset.filter(pk=request.GET.get("venue")).first()
        club = form.fields["club"].queryset.filter(pk=request.GET.get("club")).first()
        if not venue or not club:
            return HttpResponse(_("Please choose a venue and a club first."), status=400)

        content = build_venue_category_import_template_xlsx(venue, club)
        response = HttpResponse(
            content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{venue.name_en or venue.name_ar}_{club.name_en or club.name_ar}_categories_template.xlsx"'
        return response


class VenueCategoryExportView(LoginRequiredMixin, ControlPanelAccessMixin, View):
    def get(self, request, *args, **kwargs):
        form = VenueCategoryImportForm(data=request.GET)
        venue = form.fields["venue"].queryset.filter(pk=request.GET.get("venue")).first()
        club = form.fields["club"].queryset.filter(pk=request.GET.get("club")).first()
        if not venue or not club:
            return HttpResponse(_("Please choose a venue and a club first."), status=400)

        content = export_venue_categories_xlsx(venue, club)
        response = HttpResponse(
            content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{venue.name_en or venue.name_ar}_{club.name_en or club.name_ar}_categories.xlsx"'
        return response


class VenueCategoryImportView(LoginRequiredMixin, ControlPanelAccessMixin, FormView):
    template_name = "control_panel/venue_category_import.html"
    form_class = VenueCategoryImportForm

    def get_success_url(self):
        return reverse("control_panel:venue-category-import")

    def form_valid(self, form):
        venue = form.cleaned_data["venue"]
        club = form.cleaned_data["club"]
        import_file = form.cleaned_data["import_file"]
        result = import_venue_categories_xlsx(import_file, venue, club)
        return self.render_to_response(
            self.get_context_data(form=self.form_class(), result=result, venue=venue, club=club)
        )
