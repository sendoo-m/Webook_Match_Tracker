# control_panel/views/venue_control.py
#
# "Control Venue" - a single tabbed hub combining the three Control Panel
# sections a Club Manager coordinator has scoped access to (Matches, Venue
# Images, Venue Categories - see operations.permissions.
# can_access_limited_control_panel and matches.py/venue_details.py's
# test_func overrides), instead of three separate sidebar links/pages.
#
# Coordinator-only by design: a full admin has the entire Control Panel
# (many more sections than these three) and keeps using the existing
# separate pages/subnav - this hub would just be a redundant, narrower view
# for them, so test_func below requires "not a full admin, but owns a
# club" rather than can_access_limited_control_panel's broader OR.
#
# The three tabs switch client-side (see static/operations/js/
# venue-control-tabs.js) - all three tabs' data is rendered into the page
# at once (a coordinator's own scope is always small: a handful of clubs),
# so switching tabs never re-fetches anything.
#
# Add/Edit/Toggle actions still go through the existing, already-scoped
# Create/Update/ToggleActive views and URLs (unchanged) - this hub only
# consolidates the three LIST views into one page. Those actions' redirects
# (get_success_url/get_success_url_name overrides in matches.py and
# venue_details.py) bring a coordinator back here (to the right tab) after
# saving, instead of to the old standalone list page.

from itertools import groupby

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from matches.models import Club, Match, Venue, VenueImage, VenueSeatingCategory
from operations.permissions import (
    can_manage_control_panel,
    get_manageable_venue_ids_for_user,
    get_owned_club_ids,
)


class VenueControlHomeView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = "control_panel/venue_control.html"
    raise_exception = True
    permission_denied_message = "You don't have access to the control panel — your account is limited to viewing only."

    def test_func(self):
        user = self.request.user
        return not can_manage_control_panel(user) and bool(get_owned_club_ids(user))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        club_ids = get_owned_club_ids(user)
        venue_ids = get_manageable_venue_ids_for_user(user)

        matches = (
            Match.objects.filter(Q(home_club_id__in=club_ids) | Q(away_club_id__in=club_ids))
            .select_related("competition", "home_club", "away_club", "venue")
            .order_by("-event_date", "-match_start_time", "-id")
        )

        venue_images = (
            VenueImage.objects.filter(venue_id__in=venue_ids)
            .select_related("venue")
            .order_by("venue__name_ar", "sort_order")
        )

        categories = (
            VenueSeatingCategory.objects.filter(club_id__in=club_ids)
            .select_related("venue", "club")
            .order_by("club__name_ar", "sort_order", "code")
        )
        grouped_categories = [
            {"club": club, "categories": list(group)}
            for club, group in groupby(categories, key=lambda category: category.club)
        ]

        context.update({
            "page_title": _("Control Venue"),
            "matches": matches,
            "venue_images": venue_images,
            "grouped_categories": grouped_categories,
            "venue_choices": Venue.objects.filter(id__in=venue_ids).order_by("name_ar"),
            "club_choices": Club.objects.filter(id__in=club_ids).order_by("name_ar"),
        })
        return context
