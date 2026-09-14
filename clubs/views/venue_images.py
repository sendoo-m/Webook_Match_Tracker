# clubs/views/venue_images.py
#
# Lets a club's own coordinator/direct account manage their own venue's
# seating-map image and place block positions on it - the same tool
# Control Panel admins already have (control_panel/views/venue_details.py),
# scoped to only the venues/clubs this specific user is allowed to touch
# (see operations.permissions.can_manage_venue_for_club /
# get_manageable_venue_ids_for_user). Deliberately separate views from the
# Control Panel ones rather than reusing them directly - the two audiences
# need different querysets (every venue vs. only this user's own) and a
# different permission gate, and duplicating these small views is safer
# than threading a second permission model through the admin-only ones.

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from matches.models import Club, Venue, VenueImage, VenueSeatingCategory
from operations.permissions import (
    can_manage_venue_for_club,
    can_view_own_club_dashboard,
    get_manageable_venue_ids_for_user,
    get_user_club_ids,
)

from ..forms import ClubVenueImageForm


class ClubVenueAccessMixin(LoginRequiredMixin):
    """Shared dispatch gate: any user with at least one club (owner or
    club_account) can reach these views - which venue/category they can
    actually touch is then checked per-view below, never assumed from
    reaching the page at all."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not can_view_own_club_dashboard(request.user):
            raise PermissionDenied("Venue image management is only available to club accounts.")
        return super().dispatch(request, *args, **kwargs)


class ClubVenueImageListView(ClubVenueAccessMixin, ListView):
    model = VenueImage
    template_name = "operations/club_venue_image_list.html"
    context_object_name = "venue_images"

    def get_queryset(self):
        venue_ids = get_manageable_venue_ids_for_user(self.request.user)
        return (
            VenueImage.objects.filter(venue_id__in=venue_ids)
            .select_related("venue")
            .order_by("venue__name_ar", "sort_order")
        )


class ClubVenueImageCreateView(ClubVenueAccessMixin, CreateView):
    model = VenueImage
    form_class = ClubVenueImageForm
    template_name = "operations/club_venue_image_form.html"
    success_url = reverse_lazy("operations:club-venue-image-list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        venue_ids = get_manageable_venue_ids_for_user(self.request.user)
        kwargs["venue_queryset"] = Venue.objects.filter(id__in=venue_ids)
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _("Venue image added."))
        return response


class ClubVenueImageUpdateView(ClubVenueAccessMixin, UpdateView):
    model = VenueImage
    form_class = ClubVenueImageForm
    template_name = "operations/club_venue_image_form.html"
    success_url = reverse_lazy("operations:club-venue-image-list")

    def get_queryset(self):
        venue_ids = get_manageable_venue_ids_for_user(self.request.user)
        return VenueImage.objects.filter(venue_id__in=venue_ids)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        venue_ids = get_manageable_venue_ids_for_user(self.request.user)
        kwargs["venue_queryset"] = Venue.objects.filter(id__in=venue_ids)
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _("Venue image updated."))
        return response


class ClubVenueImagePositionEditorView(ClubVenueAccessMixin, View):
    """Identical interaction to control_panel's VenueImagePositionEditorView
    (pick a club, click the image to place each block) - the `club` GET
    param is restricted to the current user's own clubs only, and the image
    itself must belong to one of their manageable venues."""

    template_name = "operations/club_venue_image_positions.html"

    def get(self, request, pk, *args, **kwargs):
        venue_ids = get_manageable_venue_ids_for_user(request.user)
        image = get_object_or_404(VenueImage, pk=pk, venue_id__in=venue_ids)

        club_ids = get_user_club_ids(request.user)
        club_choices = Club.objects.filter(
            id__in=club_ids, venue_seating_categories__venue_id=image.venue_id, is_active=True
        ).distinct().order_by("name_ar")

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


class ClubVenueCategoryPositionSaveView(ClubVenueAccessMixin, View):
    """Same immediate-save-on-click behavior as
    control_panel.VenueCategoryPositionSaveView, gated by
    can_manage_venue_for_club instead of Control Panel access."""

    def post(self, request, image_pk, category_pk, *args, **kwargs):
        venue_ids = get_manageable_venue_ids_for_user(request.user)
        image = get_object_or_404(VenueImage, pk=image_pk, venue_id__in=venue_ids)
        category = get_object_or_404(VenueSeatingCategory, pk=category_pk)
        if category.venue_id != image.venue_id:
            raise Http404("This category doesn't belong to this venue's image.")
        if not can_manage_venue_for_club(request.user, category.club):
            raise PermissionDenied("You don't have permission to edit this club's block positions.")

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
