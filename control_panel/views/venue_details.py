# control_panel/views/venue_details.py
#
# Venue-level seating reference data (images + category codes) - shared
# by every club that plays at a venue, not tied to any one club. Managed
# here by coordinators/admin; consumed read-only on the club-facing
# pricing-plan page (Phase 3 of the venue-seating/pricing plan).

from itertools import groupby

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import FormView

from control_panel.forms import VenueCategoryImportForm, VenueImageForm, VenueSeatingCategoryForm
from control_panel.permissions import ControlPanelAccessMixin, ScopedControlPanelAccessMixin
from matches.models import Club, Venue, VenueImage, VenueSeatingCategory
from matches.venue_category_import_export import (
    build_venue_category_import_template_xlsx,
    export_venue_categories_xlsx,
    import_venue_categories_xlsx,
)
from operations.permissions import (
    can_access_limited_control_panel,
    can_manage_control_panel,
    can_manage_venue_for_club,
    get_manageable_venue_ids_for_user,
    get_owned_club_ids,
)

User = get_user_model()

from .base import PanelCreateView, PanelListView, PanelToggleActiveView, PanelUpdateView


class VenueImageListView(PanelListView):
    """A Club Manager coordinator can also reach this page (see
    can_access_limited_control_panel), scoped to only the venues their own
    clubs actually play HOME at - get_manageable_venue_ids_for_user already
    returns every active venue for a full admin, so this filter is a no-op
    for them and doesn't need its own branch."""

    model = VenueImage
    template_name = "control_panel/venueimage_list.html"
    context_object_name = "venue_images"
    ordering = ["venue__name_ar", "sort_order"]
    page_title = _("Venue Images")
    create_url_name = "control_panel:venue-image-create"
    create_label = _("Add Venue Image")

    def test_func(self):
        return can_access_limited_control_panel(self.request.user)

    def get_queryset(self):
        venue_ids = get_manageable_venue_ids_for_user(self.request.user)
        return super().get_queryset().filter(venue_id__in=venue_ids).select_related("venue")


class VenueImageCreateView(PanelCreateView):
    model = VenueImage
    form_class = VenueImageForm
    template_name = "control_panel/venueimage_form.html"
    success_url = reverse_lazy("control_panel:venue-image-list")
    success_message = _("Venue image created.")
    page_title = _("Add Venue Image")
    list_url_name = "control_panel:venue-image-list"

    def test_func(self):
        return can_access_limited_control_panel(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        venue_ids = get_manageable_venue_ids_for_user(self.request.user)
        kwargs["venue_queryset"] = Venue.objects.filter(id__in=venue_ids)
        return kwargs


class VenueImageUpdateView(PanelUpdateView):
    model = VenueImage
    form_class = VenueImageForm
    template_name = "control_panel/venueimage_form.html"
    success_url = reverse_lazy("control_panel:venue-image-list")
    success_message = _("Venue image updated.")
    page_title = _("Edit Venue Image")
    list_url_name = "control_panel:venue-image-list"

    def test_func(self):
        return can_access_limited_control_panel(self.request.user)

    def get_queryset(self):
        venue_ids = get_manageable_venue_ids_for_user(self.request.user)
        return super().get_queryset().filter(venue_id__in=venue_ids)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        venue_ids = get_manageable_venue_ids_for_user(self.request.user)
        kwargs["venue_queryset"] = Venue.objects.filter(id__in=venue_ids)
        return kwargs


class VenueImageToggleActiveView(PanelToggleActiveView):
    model = VenueImage
    success_url_name = "control_panel:venue-image-list"

    def test_func(self):
        return can_access_limited_control_panel(self.request.user)

    def get_object(self, pk):
        venue_ids = get_manageable_venue_ids_for_user(self.request.user)
        return get_object_or_404(self.model, pk=pk, venue_id__in=venue_ids)


class VenueImagePositionEditorView(LoginRequiredMixin, ScopedControlPanelAccessMixin, View):
    """Lets a coordinator/admin click on a venue's seating-map image to
    place one point per seating category (block) - the price badge shown
    to clubs/SPL later gets positioned there. One club at a time (a venue
    image is shared, but categories and their positions are scoped per
    (venue, club) - see VenueSeatingCategory's own docstring), picked via
    the `club` GET param."""

    template_name = "control_panel/venue_image_positions.html"

    def get(self, request, pk, *args, **kwargs):
        venue_ids = get_manageable_venue_ids_for_user(request.user)
        image = get_object_or_404(VenueImage, pk=pk, venue_id__in=venue_ids)

        club_choices = Club.objects.filter(
            venue_seating_categories__venue_id=image.venue_id, is_active=True
        ).distinct().order_by("name_ar")
        if not can_manage_control_panel(request.user):
            club_choices = club_choices.filter(id__in=get_owned_club_ids(request.user))

        selected_club_id = request.GET.get("club", "").strip()
        selected_club = club_choices.filter(pk=selected_club_id).first() if selected_club_id else None
        if not selected_club and club_choices.count() == 1:
            # A coordinator with exactly one club at this venue never needs
            # to pick it themselves - skip straight to their own categories.
            selected_club = club_choices.first()

        categories = []
        if selected_club:
            categories = list(
                VenueSeatingCategory.objects.filter(venue_id=image.venue_id, club=selected_club)
                .order_by("sort_order", "code")
            )

        return render(request, self.template_name, {
            "page_title": _("Block Positions"),
            "image": image,
            "club_choices": club_choices,
            "selected_club": selected_club,
            "categories": categories,
            # A plain list, not a pre-dumped JSON string - the |json_script
            # filter in the template does its own json.dumps() on this
            # value, so dumping it here too would double-encode it into a
            # JSON string containing escaped JSON text instead of a real
            # array, and JS's JSON.parse() would hand back a string with no
            # .forEach(), silently breaking every click handler below it.
            "categories_json": [
                {
                    "id": category.id,
                    "code": category.code,
                    "x": category.position_x,
                    "y": category.position_y,
                    "placed": category.has_position and category.position_image_id == image.id,
                }
                for category in categories
            ],
        })


class VenueCategoryPositionSaveView(LoginRequiredMixin, ScopedControlPanelAccessMixin, View):
    """AJAX-only: saves (or clears, when x/y are omitted) one category's
    point on one venue image. Immediate-save-on-click rather than a batch
    "Save" button, so a placement is never lost if the coordinator
    navigates away mid-session."""

    def post(self, request, image_pk, category_pk, *args, **kwargs):
        venue_ids = get_manageable_venue_ids_for_user(request.user)
        image = get_object_or_404(VenueImage, pk=image_pk, venue_id__in=venue_ids)
        category = get_object_or_404(VenueSeatingCategory, pk=category_pk)
        if category.venue_id != image.venue_id:
            raise Http404("This category doesn't belong to this venue's image.")
        if not can_manage_venue_for_club(request.user, category.club):
            raise Http404("This category doesn't belong to this venue's image.")

        x = request.POST.get("x")
        y = request.POST.get("y")
        if x is None or y is None:
            category.position_image = None
            category.position_x = None
            category.position_y = None
        else:
            try:
                x = max(0.0, min(100.0, float(x)))
                y = max(0.0, min(100.0, float(y)))
            except ValueError:
                return JsonResponse({"ok": False, "error": "Invalid coordinates."}, status=400)
            category.position_image = image
            category.position_x = x
            category.position_y = y

        category.save(update_fields=["position_image", "position_x", "position_y"])
        return JsonResponse({"ok": True})


class VenueSeatingCategoryListView(PanelListView):
    """Grouped by club rather than one flat table - with 18 clubs and up to
    ~200 categories for a single club, a flat paginated list makes it hard
    to find anything. Ordering by club first (not venue first, as before)
    is what makes the groupby() in get_context_data valid - groupby only
    groups consecutive items, so the queryset's own ordering has to match
    the grouping key.

    A Club Manager coordinator can also reach this page (see
    can_access_limited_control_panel), scoped to only their own club(s)'
    categories - never another club's, even one sharing the same venue."""

    model = VenueSeatingCategory
    template_name = "control_panel/venueseatingcategory_list.html"
    context_object_name = "categories"
    ordering = ["club__name_ar", "sort_order", "code"]
    page_title = _("Venue Seating Categories")
    create_url_name = "control_panel:venue-category-create"
    create_label = _("Add Category")
    paginate_by = None

    def test_func(self):
        return can_access_limited_control_panel(self.request.user)

    def get_queryset(self):
        queryset = super().get_queryset().select_related("venue", "club")

        if not can_manage_control_panel(self.request.user):
            queryset = queryset.filter(club_id__in=get_owned_club_ids(self.request.user))

        club = self.request.GET.get("club", "").strip()
        if club:
            queryset = queryset.filter(club_id=club)

        coordinator = self.request.GET.get("coordinator", "").strip()
        if coordinator:
            queryset = queryset.filter(club__owner_id=coordinator)

        venue = self.request.GET.get("venue", "").strip()
        if venue:
            queryset = queryset.filter(venue_id=venue)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        is_full_admin = can_manage_control_panel(self.request.user)
        categories = context[self.context_object_name]
        context["grouped_categories"] = [
            {"club": club, "categories": list(group)}
            for club, group in groupby(categories, key=lambda category: category.club)
        ]
        if is_full_admin:
            context["club_choices"] = Club.objects.filter(is_active=True).order_by("name_ar")
            context["venue_choices"] = Venue.objects.filter(is_active=True).order_by("name_ar")
        else:
            owned_club_ids = get_owned_club_ids(self.request.user)
            context["club_choices"] = Club.objects.filter(id__in=owned_club_ids).order_by("name_ar")
            venue_ids = get_manageable_venue_ids_for_user(self.request.user)
            context["venue_choices"] = Venue.objects.filter(id__in=venue_ids).order_by("name_ar")
        context["coordinator_choices"] = User.objects.filter(
            owned_clubs__isnull=False, is_active=True
        ).distinct().order_by("username")
        context["selected_club"] = self.request.GET.get("club", "")
        context["selected_coordinator"] = self.request.GET.get("coordinator", "")
        context["selected_venue"] = self.request.GET.get("venue", "")
        context["has_active_filters"] = any([
            context["selected_club"], context["selected_coordinator"], context["selected_venue"],
        ])
        context["is_full_admin"] = is_full_admin
        if not is_full_admin:
            context.pop("create_url", None)
        return context


class VenueSeatingCategoryCreateView(PanelCreateView):
    model = VenueSeatingCategory
    form_class = VenueSeatingCategoryForm
    template_name = "control_panel/venueseatingcategory_form.html"
    success_url = reverse_lazy("control_panel:venue-category-list")
    success_message = _("Venue seating category created.")
    page_title = _("Add Venue Seating Category")
    list_url_name = "control_panel:venue-category-list"

    def test_func(self):
        return can_access_limited_control_panel(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if not can_manage_control_panel(self.request.user):
            venue_ids = get_manageable_venue_ids_for_user(self.request.user)
            kwargs["venue_queryset"] = Venue.objects.filter(id__in=venue_ids)
            kwargs["club_queryset"] = Club.objects.filter(id__in=get_owned_club_ids(self.request.user))
        return kwargs


class VenueSeatingCategoryUpdateView(PanelUpdateView):
    model = VenueSeatingCategory
    form_class = VenueSeatingCategoryForm
    template_name = "control_panel/venueseatingcategory_form.html"
    success_url = reverse_lazy("control_panel:venue-category-list")
    success_message = _("Venue seating category updated.")
    page_title = _("Edit Venue Seating Category")
    list_url_name = "control_panel:venue-category-list"

    def test_func(self):
        return can_access_limited_control_panel(self.request.user)

    def get_queryset(self):
        queryset = super().get_queryset()
        if not can_manage_control_panel(self.request.user):
            queryset = queryset.filter(club_id__in=get_owned_club_ids(self.request.user))
        return queryset

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if not can_manage_control_panel(self.request.user):
            venue_ids = get_manageable_venue_ids_for_user(self.request.user)
            kwargs["venue_queryset"] = Venue.objects.filter(id__in=venue_ids)
            kwargs["club_queryset"] = Club.objects.filter(id__in=get_owned_club_ids(self.request.user))
        return kwargs


class VenueSeatingCategoryToggleActiveView(PanelToggleActiveView):
    model = VenueSeatingCategory
    success_url_name = "control_panel:venue-category-list"

    def test_func(self):
        return can_access_limited_control_panel(self.request.user)

    def get_object(self, pk):
        obj = get_object_or_404(self.model, pk=pk)
        if not can_manage_control_panel(self.request.user) and obj.club_id not in get_owned_club_ids(self.request.user):
            raise Http404("This category doesn't belong to one of your clubs.")
        return obj


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
