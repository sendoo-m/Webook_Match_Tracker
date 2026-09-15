import shutil
import tempfile
from datetime import time
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from matches.models import Club, Competition, Match, UserCompetitionAccess, Venue, VenueImage, VenueSeatingCategory
from notifications.models import Notification
from operations.models import ClubPricingPlan, ClubPricingPlanCategoryPrice, MatchActivityLog
from operations.permissions import (
    can_access_spl_approval_area,
    can_approve_pricing_plan,
    can_confirm_home_match_submission,
    can_manage_home_match,
    can_publish_match_from_club_dashboard,
    can_submit_home_match_to_spl,
    can_upload_home_match_pricing_plan,
    can_view_club_match,
    can_view_own_club_dashboard,
    get_visible_matches,
    user_can_manage_match,
)


class ClubDashboardPermissionsTestBase(TestCase):
    """Shared fixtures: three clubs (A, B, C), each owned by its own user,
    one competition A and B are granted access to (C is not), and one
    fixture where A hosts and B visits. Real ORM relations, not mocks, so
    these tests exercise the actual permission code path end to end."""

    @classmethod
    def setUpTestData(cls):
        cls.competition = Competition.objects.create(name_ar="دوري تجريبي", name_en="Test League")
        cls.other_competition = Competition.objects.create(name_ar="دوري آخر", name_en="Other League")

        cls.user_a = User.objects.create_user(username="_test_club_a", password="pw")
        cls.user_b = User.objects.create_user(username="_test_club_b", password="pw")
        cls.user_c = User.objects.create_user(username="_test_club_c", password="pw")

        cls.club_a = Club.objects.create(name_ar="نادي أ", name_en="Club A", owner=cls.user_a)
        cls.club_b = Club.objects.create(name_ar="نادي ب", name_en="Club B", owner=cls.user_b)
        cls.club_c = Club.objects.create(name_ar="نادي ج", name_en="Club C", owner=cls.user_c)

        UserCompetitionAccess.objects.create(user=cls.user_a, competition=cls.competition)
        UserCompetitionAccess.objects.create(user=cls.user_b, competition=cls.competition)
        # user_c deliberately gets no access to `competition` at all - an
        # unrelated third club with no relation to the fixture below.

        club_manager_group, _ = Group.objects.get_or_create(name="Club Manager")
        for u in (cls.user_a, cls.user_b, cls.user_c):
            u.groups.add(club_manager_group)

        # Real "Club Viewer" accounts (Club.club_account, a separate slot
        # from the Club Manager coordinators above) for clubs A and B - the
        # only accounts that can still reach the Club Dashboard's own
        # landing page (ClubDashboardView) after the 2026-09-15 product
        # decision to remove it from Club Manager.
        club_viewer_group, _ = Group.objects.get_or_create(name="Club Viewer")
        cls.club_viewer_a = User.objects.create_user(username="_test_club_viewer_a", password="pw")
        cls.club_viewer_a.groups.add(club_viewer_group)
        cls.club_a.club_account = cls.club_viewer_a
        cls.club_a.save(update_fields=["club_account"])

        cls.club_viewer_b = User.objects.create_user(username="_test_club_viewer_b", password="pw")
        cls.club_viewer_b.groups.add(club_viewer_group)
        cls.club_b.club_account = cls.club_viewer_b
        cls.club_b.save(update_fields=["club_account"])

        # A hosts, B visits.
        cls.match = Match.objects.create(
            competition=cls.competition,
            home_club=cls.club_a,
            away_club=cls.club_b,
            slug="_test-club-a-vs-club-b",
            title_ar="نادي أ ضد نادي ب",
            title_en="Club A vs Club B",
        )

        operations_manager_group, _ = Group.objects.get_or_create(name="Operations Manager")
        cls.manager_user = User.objects.create_user(username="_test_ops_manager", password="pw")
        cls.manager_user.groups.add(operations_manager_group)

        viewer_group, _ = Group.objects.get_or_create(name="Viewer")
        cls.viewer_user = User.objects.create_user(username="_test_viewer", password="pw")
        cls.viewer_user.groups.add(viewer_group)

        cls.superuser = User.objects.create_superuser(
            username="_test_super", password="pw", email="_test_super@example.com"
        )

        # A fourth club with no owner, and a fixture between it and Club C -
        # entirely unrelated to A/B, for isolation tests on the club
        # dashboard views (Phase 3).
        cls.club_d = Club.objects.create(name_ar="نادي د", name_en="Club D")
        cls.unrelated_match = Match.objects.create(
            competition=cls.other_competition,
            home_club=cls.club_c,
            away_club=cls.club_d,
            slug="_test-club-c-vs-club-d",
            title_ar="نادي ج ضد نادي د",
            title_en="Club C vs Club D",
        )


class VisibilityTests(ClubDashboardPermissionsTestBase):
    def test_club_manager_coordinator_no_longer_sees_the_club_dashboard(self):
        # Product decision (2026-09-15): the Club Dashboard's landing page
        # is reserved for a real "Club Viewer" account - a "Club Manager"
        # coordinator (user_a's fixture group here) no longer sees it, even
        # though they still keep the match detail page and the pricing-
        # plan upload/submit/confirm/download flow exactly as before.
        self.assertFalse(can_view_own_club_dashboard(self.user_a))

    def test_unrelated_club_manager_also_does_not_see_the_dashboard(self):
        self.assertFalse(can_view_own_club_dashboard(self.user_c))

    def test_can_view_club_match_true_for_home_club(self):
        self.assertTrue(can_view_club_match(self.user_a, self.match))

    def test_can_view_club_match_true_for_away_club(self):
        self.assertTrue(can_view_club_match(self.user_b, self.match))

    def test_can_view_club_match_false_for_unrelated_club(self):
        self.assertFalse(can_view_club_match(self.user_c, self.match))

    def test_get_visible_matches_unchanged_for_home_club(self):
        """Existing behavior: the home club sees the match through the
        existing scoped queryset, exactly as before this change."""
        visible = get_visible_matches(self.user_a, Match.objects.all())
        self.assertIn(self.match, visible)

    def test_get_visible_matches_unchanged_for_away_club(self):
        """Existing behavior preserved on purpose: get_visible_matches
        still does NOT show the away club this match - only the new
        can_view_club_match function does. No page today gets Away
        matches added to it by this change."""
        visible = get_visible_matches(self.user_b, Match.objects.all())
        self.assertNotIn(self.match, visible)

    def test_get_visible_matches_unchanged_for_unrelated_club(self):
        visible = get_visible_matches(self.user_c, Match.objects.all())
        self.assertNotIn(self.match, visible)


class ActionPermissionTests(ClubDashboardPermissionsTestBase):
    def test_home_club_can_manage_home_match(self):
        self.assertTrue(can_manage_home_match(self.user_a, self.match))
        self.assertTrue(user_can_manage_match(self.user_a, self.match))

    def test_away_club_cannot_manage_match(self):
        self.assertFalse(can_manage_home_match(self.user_b, self.match))
        self.assertFalse(user_can_manage_match(self.user_b, self.match))

    def test_unrelated_club_cannot_manage_match(self):
        self.assertFalse(can_manage_home_match(self.user_c, self.match))

    def test_home_club_without_competition_access_cannot_manage(self):
        """Existing rule preserved: home club alone isn't enough without
        the competition grant too."""
        UserCompetitionAccess.objects.filter(user=self.user_a, competition=self.competition).delete()
        self.assertFalse(can_manage_home_match(self.user_a, self.match))

    def test_home_club_can_upload_pricing_plan_when_state_allows(self):
        self.assertTrue(can_upload_home_match_pricing_plan(self.user_a, self.match))

    def test_away_club_cannot_upload_pricing_plan(self):
        self.assertFalse(can_upload_home_match_pricing_plan(self.user_b, self.match))

    def test_home_club_cannot_upload_once_plan_approved(self):
        self.match.ticketing_plan_approved = True
        self.match.save(update_fields=["ticketing_plan_approved"])
        self.assertFalse(can_upload_home_match_pricing_plan(self.user_a, self.match))

    def test_home_club_cannot_submit_without_a_plan_file(self):
        self.assertFalse(can_submit_home_match_to_spl(self.user_a, self.match))

    def test_away_club_cannot_submit_to_spl(self):
        self.assertFalse(can_submit_home_match_to_spl(self.user_b, self.match))

    def test_confirm_home_match_submission_is_always_false_today(self):
        """No club-submission model/field exists yet - this must stay
        False for every role until Phase 5 adds one, home club included."""
        self.assertFalse(can_confirm_home_match_submission(self.user_a, self.match))
        self.assertFalse(can_confirm_home_match_submission(self.manager_user, self.match))

    def test_club_user_can_never_approve_pricing_plan(self):
        self.assertFalse(can_approve_pricing_plan(self.user_a, self.match))
        self.assertFalse(can_approve_pricing_plan(self.user_b, self.match))

    def test_manager_and_viewer_can_approve_pricing_plan(self):
        self.assertTrue(can_approve_pricing_plan(self.manager_user, self.match))
        self.assertTrue(can_approve_pricing_plan(self.viewer_user, self.match))

    def test_club_user_can_never_publish_from_club_dashboard(self):
        self.assertFalse(can_publish_match_from_club_dashboard(self.user_a, self.match))
        self.assertFalse(can_publish_match_from_club_dashboard(self.user_b, self.match))

    def test_manager_can_publish_from_club_dashboard(self):
        self.assertTrue(can_publish_match_from_club_dashboard(self.manager_user, self.match))


class SPLApprovalsAccessTests(ClubDashboardPermissionsTestBase):
    def test_can_access_spl_approval_area_false_for_club_user(self):
        self.assertFalse(can_access_spl_approval_area(self.user_a))
        self.assertFalse(can_access_spl_approval_area(self.user_b))

    def test_can_access_spl_approval_area_true_for_manager_and_viewer(self):
        self.assertTrue(can_access_spl_approval_area(self.manager_user))
        self.assertTrue(can_access_spl_approval_area(self.viewer_user))

    def test_unauthorized_club_manager_gets_denied_on_spl_approvals_page(self):
        """PermissionDenied here is caught project-wide by
        FriendlyPermissionDeniedMiddleware (operations/middleware.py),
        which turns it into a redirect + toast instead of a raw 403 page -
        the same behavior every other PermissionDenied in this app already
        gets. What matters is that the page's own content (the SPL
        approval rows) never renders and never reaches the response."""
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get("/operations/reports/spl/approvals/")
        self.assertEqual(response.status_code, 302)
        # No leaked match/club data - dispatch() raises before
        # get_context_data ever builds the row data.
        self.assertNotIn(b"Club A", response.content)
        self.assertNotIn(b"Club B", response.content)

    def test_operations_manager_still_has_access(self):
        client = Client()
        client.login(username="_test_ops_manager", password="pw")
        response = client.get("/operations/reports/spl/approvals/")
        self.assertEqual(response.status_code, 200)

    def test_viewer_still_has_access(self):
        client = Client()
        client.login(username="_test_viewer", password="pw")
        response = client.get("/operations/reports/spl/approvals/")
        self.assertEqual(response.status_code, 200)

    def test_away_club_cannot_post_plan_confirm_directly(self):
        """These three views already raised PermissionDenied for ANY club
        user before this phase - the friendly middleware turns that into
        a 302 (see test_unauthorized_club_manager_gets_denied_on_spl_approvals_page),
        not a raw 403. Confirms the pre-existing protection is real."""
        client = Client()
        client.login(username="_test_club_b", password="pw")
        response = client.post(f"/operations/matches/{self.match.pk}/spl-plan-confirm/")
        self.assertEqual(response.status_code, 302)
        self.match.refresh_from_db()
        self.assertFalse(self.match.ticketing_plan_approved)

    def test_home_club_cannot_post_plan_confirm_directly(self):
        """Confirming the SPL ticketing plan has always been Viewer/manager
        only, even for the home club running the match - unchanged here."""
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.post(f"/operations/matches/{self.match.pk}/spl-plan-confirm/")
        self.assertEqual(response.status_code, 302)
        self.match.refresh_from_db()
        self.assertFalse(self.match.ticketing_plan_approved)

    def test_away_club_cannot_post_tickets_confirm_directly(self):
        client = Client()
        client.login(username="_test_club_b", password="pw")
        response = client.post(f"/operations/matches/{self.match.pk}/spl-tickets-confirm/")
        self.assertEqual(response.status_code, 302)
        self.match.refresh_from_db()
        self.assertFalse(self.match.spl_tickets_sent)

    def test_away_club_cannot_post_plan_approval_upload_directly(self):
        client = Client()
        client.login(username="_test_club_b", password="pw")
        response = client.post(f"/operations/matches/{self.match.pk}/spl-plan-approval-upload/")
        self.assertEqual(response.status_code, 302)
        self.match.refresh_from_db()
        self.assertFalse(bool(self.match.plan_approval_file))


class NoRegressionTests(ClubDashboardPermissionsTestBase):
    """Confirms the existing, already-shipped Operations Dashboard behavior
    this phase must not touch is still exactly what it was before."""

    def test_user_can_manage_match_unchanged_for_home_club(self):
        self.assertTrue(user_can_manage_match(self.user_a, self.match))

    def test_user_can_manage_match_unchanged_for_away_club(self):
        self.assertFalse(user_can_manage_match(self.user_b, self.match))

    def test_user_can_manage_match_unchanged_for_superuser(self):
        self.assertTrue(user_can_manage_match(self.superuser, self.match))

    def test_operations_manager_still_excluded_from_match_management(self):
        """Documented existing behavior: Operations Manager gets full
        visibility/Control Panel access but NOT day-to-day match
        management - unaffected by this phase's changes."""
        self.assertFalse(user_can_manage_match(self.manager_user, self.match))

    def test_home_club_can_still_send_to_cms(self):
        """SendToCMSView's own permission gate (require_match_access) is
        untouched - the home club coordinator can still reach it exactly
        as before. Not ready for CMS yet (no checklist items), so this
        only asserts the permission gate itself, not a full send.
        """
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.post(f"/operations/matches/{self.match.pk}/send-to-cms/")
        # Not a PermissionDenied (403) - the coordinator is allowed to
        # attempt this action; it simply isn't ready yet (400) because no
        # checklist items exist on this test match.
        self.assertNotEqual(response.status_code, 403)

    def test_away_club_still_blocked_from_send_to_cms(self):
        """SendToCMSView scopes its queryset through get_visible_matches
        first (home-club-only), so for the away club this match is not
        merely off-limits - it's not even in scope, and get_object_or_404
        raises Http404 before require_match_access is ever reached.
        Existing, unchanged behavior."""
        client = Client()
        client.login(username="_test_club_b", password="pw")
        response = client.post(f"/operations/matches/{self.match.pk}/send-to-cms/")
        self.assertEqual(response.status_code, 404)


# --- Phase 3: Club Dashboard view tests ----------------------------------


class ClubDashboardAccessTests(ClubDashboardPermissionsTestBase):
    def test_club_viewer_can_open_own_dashboard(self):
        client = Client()
        client.login(username="_test_club_viewer_a", password="pw")
        response = client.get("/operations/club-dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "operations/club_dashboard.html")

    def test_club_manager_coordinator_is_denied(self):
        """Product decision (2026-09-15): the dashboard's own landing page
        is Club Viewer-only now - a Club Manager coordinator (owner of the
        same club) gets redirected away instead of the page itself."""
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get("/operations/club-dashboard/")
        self.assertEqual(response.status_code, 302)

    def test_user_with_no_club_is_denied(self):
        """Operations Manager owns no club at all - denied, redirected by
        the same FriendlyPermissionDeniedMiddleware every other denial in
        this app goes through, not a raw 403 page."""
        client = Client()
        client.login(username="_test_ops_manager", password="pw")
        response = client.get("/operations/club-dashboard/")
        self.assertEqual(response.status_code, 302)

    def test_viewer_is_denied(self):
        client = Client()
        client.login(username="_test_viewer", password="pw")
        response = client.get("/operations/club-dashboard/")
        self.assertEqual(response.status_code, 302)

    def test_query_parameter_cannot_widen_club_scope(self):
        """There is no club_id/type parameter that selects a different
        club - the schedule view only ever reads
        get_user_club_ids(request.user). Club C/D's unrelated match must
        never appear no matter what's appended to the URL."""
        client = Client()
        client.login(username="_test_club_viewer_a", password="pw")
        response = client.get(
            "/operations/club-dashboard/schedule/",
            {"club_id": self.club_c.pk, "club": self.club_c.pk},
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertNotIn("Club C", content)
        # Not "Club D" - that's a substring of the page's own title "Club
        # Dashboard". The unrelated match's slug is unambiguous instead.
        self.assertNotIn(self.unrelated_match.slug, content)


class ClubDashboardHomepageTests(ClubDashboardPermissionsTestBase):
    """The homepage (ClubDashboardView) is a snapshot: identity, home
    venue, and the next round's fixtures (upcoming_rows) - not the full,
    filterable match list, which moved to ClubDashboardScheduleView."""

    def test_home_match_appears_for_home_club(self):
        client = Client()
        client.login(username="_test_club_viewer_a", password="pw")
        response = client.get("/operations/club-dashboard/")
        self.assertIn(self.match, [row["match"] for row in response.context["upcoming_rows"]])

    def test_table_shows_round_not_competition(self):
        self.match.round_number = 7
        self.match.save(update_fields=["round_number"])
        client = Client()
        client.login(username="_test_club_viewer_a", password="pw")
        response = client.get("/operations/club-dashboard/")
        self.assertContains(response, "<th>Round</th>")
        self.assertNotContains(response, "<th>Competition</th>")

    def test_away_match_appears_for_away_club(self):
        """The whole point of Phase 3: unlike get_visible_matches, the
        club dashboard shows the club its Away fixtures too."""
        client = Client()
        client.login(username="_test_club_viewer_b", password="pw")
        response = client.get("/operations/club-dashboard/")
        self.assertIn(self.match, [row["match"] for row in response.context["upcoming_rows"]])

    def test_unrelated_match_never_appears(self):
        client = Client()
        client.login(username="_test_club_viewer_a", password="pw")
        response = client.get("/operations/club-dashboard/")
        matches = [row["match"] for row in response.context["upcoming_rows"]]
        self.assertNotIn(self.unrelated_match, matches)

    def test_club_identity_shown(self):
        client = Client()
        client.login(username="_test_club_viewer_a", password="pw")
        response = client.get("/operations/club-dashboard/")
        self.assertEqual(response.context["club"], self.club_a)

    def test_home_venue_derived_from_home_matches(self):
        venue = Venue.objects.create(name_ar="_ملعب تجريبي", name_en="_Test Home Venue")
        self.match.venue = venue
        self.match.save(update_fields=["venue"])
        client = Client()
        client.login(username="_test_club_viewer_a", password="pw")
        response = client.get("/operations/club-dashboard/")
        self.assertEqual(response.context["venue"], venue)

    def test_home_venue_never_taken_from_an_away_fixture(self):
        """club_b (the away side of self.match) must not have self.match's
        venue attributed to it - only a club's own HOME matches count."""
        venue = Venue.objects.create(name_ar="_ملعب تجريبي ب", name_en="_Test Home Venue B")
        self.match.venue = venue
        self.match.save(update_fields=["venue"])
        client = Client()
        client.login(username="_test_club_viewer_b", password="pw")
        response = client.get("/operations/club-dashboard/")
        self.assertIsNone(response.context["venue"])

    def test_total_capacity_sums_active_seating_categories(self):
        venue = Venue.objects.create(name_ar="_ملعب تجريبي ج", name_en="_Test Home Venue C")
        self.match.venue = venue
        self.match.save(update_fields=["venue"])
        VenueSeatingCategory.objects.create(
            venue=venue, club=self.club_a, code="_TEST CAT 1", seat_count=1000,
        )
        VenueSeatingCategory.objects.create(
            venue=venue, club=self.club_a, code="_TEST CAT 2", seat_count=500,
        )
        VenueSeatingCategory.objects.create(
            venue=venue, club=self.club_a, code="_TEST CAT INACTIVE", seat_count=999, is_active=False,
        )
        client = Client()
        client.login(username="_test_club_viewer_a", password="pw")
        response = client.get("/operations/club-dashboard/")
        self.assertEqual(response.context["total_capacity"], 1500)

    def test_upcoming_rows_exclude_a_finished_match(self):
        self.match.round_number = 5
        self.match.event_date = timezone.localtime().date() - timezone.timedelta(days=30)
        self.match.match_start_time = timezone.datetime.min.time()
        self.match.save(update_fields=["round_number", "event_date", "match_start_time"])
        client = Client()
        client.login(username="_test_club_viewer_a", password="pw")
        response = client.get("/operations/club-dashboard/")
        self.assertNotIn(self.match, [row["match"] for row in response.context["upcoming_rows"]])

    def test_upcoming_rows_include_a_match_with_no_date_yet(self):
        """A round-based cutoff, not a raw "event_date >= today" filter: a
        match whose date/time isn't confirmed yet (TBC) has no way to be
        judged "finished" or attributed to a specific point in time, so it
        must still show up on the homepage rather than being silently
        dropped by a plain date comparison."""
        self.match.round_number = 5
        self.match.event_date = None
        self.match.save(update_fields=["round_number", "event_date"])
        client = Client()
        client.login(username="_test_club_viewer_a", password="pw")
        response = client.get("/operations/club-dashboard/")
        self.assertIn(self.match, [row["match"] for row in response.context["upcoming_rows"]])

    def test_changing_match_id_in_url_does_not_leak_other_clubs_data(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get(f"/operations/club-dashboard/matches/{self.unrelated_match.pk}/")
        self.assertEqual(response.status_code, 302)

    def test_get_visible_matches_not_used_to_gate_away_visibility(self):
        """Confirms the dashboard's own queryset (not get_visible_matches)
        is what makes Away matches visible - get_visible_matches itself
        still excludes them, proven in VisibilityTests above."""
        from operations.permissions import get_visible_matches

        self.assertNotIn(self.match, get_visible_matches(self.user_b, Match.objects.all()))

    def test_old_pages_do_not_show_away_matches(self):
        """The existing Matches list (MatchListView) must still be
        home-only for the away club - untouched by this phase."""
        client = Client()
        client.login(username="_test_club_b", password="pw")
        response = client.get("/operations/matches/")
        matches = list(response.context["matches"])
        self.assertNotIn(self.match, matches)


class ClubDashboardActionTests(ClubDashboardPermissionsTestBase):
    def test_home_match_detail_shows_no_management_controls(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get(f"/operations/club-dashboard/matches/{self.match.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["can_approve_pricing_plan"])
        self.assertFalse(response.context["can_publish_match"])
        self.assertTrue(response.context["can_manage_home_match"])

    def test_away_match_detail_shows_follow_up_only(self):
        client = Client()
        client.login(username="_test_club_b", password="pw")
        response = client.get(f"/operations/club-dashboard/matches/{self.match.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["is_home"])
        self.assertFalse(response.context["can_manage_home_match"])
        self.assertFalse(response.context["can_upload_pricing_plan"])
        self.assertContains(response, "Away Match")

    def test_direct_access_to_unrelated_match_is_denied(self):
        client = Client()
        client.login(username="_test_club_b", password="pw")
        response = client.get(f"/operations/club-dashboard/matches/{self.unrelated_match.pk}/")
        self.assertEqual(response.status_code, 302)

    def test_club_cannot_approve_pricing_plan_from_detail_page(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get(f"/operations/club-dashboard/matches/{self.match.pk}/")
        self.assertFalse(response.context["can_approve_pricing_plan"])

    def test_club_cannot_publish_from_detail_page(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get(f"/operations/club-dashboard/matches/{self.match.pk}/")
        self.assertFalse(response.context["can_publish_match"])

    def test_club_cannot_reach_spl_approvals_from_here_either(self):
        """Same protection Phase 2 added, confirmed still in effect."""
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get("/operations/reports/spl/approvals/")
        self.assertEqual(response.status_code, 302)

    def test_match_status_shows_the_simplified_three_states_not_ticket_sale_status(self):
        """Product decision: "Match Status" and "Ticket Sale Status" said
        the same thing to a club - consolidated into one simplified
        Match Status (In Progress/Live/Finished), matching the wording
        already used on the club's other tables."""
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get(f"/operations/club-dashboard/matches/{self.match.pk}/")
        self.assertNotContains(response, "Ticket Sale Status")
        self.assertContains(response, "Match Status")

    def test_audience_split_shown_on_match_detail(self):
        plan = ClubPricingPlan.objects.create(
            match=self.match, club=self.club_a, version=1, home_percentage=70,
        )
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get(f"/operations/club-dashboard/matches/{self.match.pk}/")
        self.assertContains(response, "70% Home / 30% Away")

    def test_match_start_time_shown_in_12_hour_format(self):
        """System review request: club-facing pages show times as
        "04:30 PM", not the internal 24-hour "16:30"."""
        self.match.match_start_time = time(16, 30)
        self.match.save(update_fields=["match_start_time"])
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get(f"/operations/club-dashboard/matches/{self.match.pk}/")
        self.assertContains(response, "04:30 PM")
        self.assertNotContains(response, "16:30")

    def test_competition_logo_shown_next_to_its_name_when_set(self):
        self.competition.logo = _tiny_png()
        self.competition.save(update_fields=["logo"])
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get(f"/operations/club-dashboard/matches/{self.match.pk}/")
        self.assertContains(response, "competition-logo")

    def test_no_broken_image_when_competition_has_no_logo(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get(f"/operations/club-dashboard/matches/{self.match.pk}/")
        self.assertNotContains(response, "competition-logo")
        self.assertContains(response, str(self.competition))

    def test_recent_activity_limited_to_three_with_a_view_all_link(self):
        for i in range(5):
            MatchActivityLog.objects.create(
                match=self.match, action=MatchActivityLog.Action.STATUS_CHANGED, description=f"Event {i}",
            )
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get(f"/operations/club-dashboard/matches/{self.match.pk}/")
        self.assertEqual(len(response.context["recent_activity"]), 3)
        self.assertContains(response, f"/operations/club-dashboard/matches/{self.match.pk}/activity/")


class ClubDashboardMatchActivityTests(ClubDashboardPermissionsTestBase):
    def setUp(self):
        for i in range(25):
            MatchActivityLog.objects.create(
                match=self.match, action=MatchActivityLog.Action.STATUS_CHANGED, description=f"Event {i}",
            )

    def test_home_club_can_view_full_activity(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get(f"/operations/club-dashboard/matches/{self.match.pk}/activity/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["activity_logs"]), 20)

    def test_away_club_can_also_view_it(self):
        client = Client()
        client.login(username="_test_club_b", password="pw")
        response = client.get(f"/operations/club-dashboard/matches/{self.match.pk}/activity/")
        self.assertEqual(response.status_code, 200)

    def test_unrelated_club_is_denied(self):
        client = Client()
        client.login(username="_test_club_c", password="pw")
        response = client.get(f"/operations/club-dashboard/matches/{self.match.pk}/activity/")
        self.assertEqual(response.status_code, 302)

    def test_second_page_shows_the_rest(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get(f"/operations/club-dashboard/matches/{self.match.pk}/activity/", {"page": 2})
        self.assertEqual(len(response.context["activity_logs"]), 5)


class ClubDashboardUITests(ClubDashboardPermissionsTestBase):
    def test_empty_state_renders_for_club_with_no_matches(self):
        club_viewer_group = Group.objects.get(name="Club Viewer")
        no_match_user = User.objects.create_user(username="_test_club_e", password="pw")
        no_match_user.groups.add(club_viewer_group)
        Club.objects.create(name_ar="نادي هـ", name_en="Club E", club_account=no_match_user)
        client = Client()
        client.login(username="_test_club_e", password="pw")
        response = client.get("/operations/club-dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["upcoming_rows"]), 0)

        response2 = client.get("/operations/club-dashboard/schedule/")
        self.assertEqual(response2.status_code, 200)
        self.assertEqual(len(response2.context["rows"]), 0)

    def test_schedule_table_shows_round_not_competition(self):
        """The Competition FILTER stays (still useful) - only the table's
        own column changes from Competition to Round."""
        client = Client()
        client.login(username="_test_club_viewer_a", password="pw")
        response = client.get("/operations/club-dashboard/schedule/")
        self.assertContains(response, "<th>Round</th>")
        self.assertNotContains(response, "<th>Competition</th>")

    def test_type_filter_narrows_to_home_only(self):
        client = Client()
        client.login(username="_test_club_viewer_a", password="pw")
        response = client.get("/operations/club-dashboard/schedule/", {"type": "home"})
        for row in response.context["rows"]:
            self.assertTrue(row["is_home"])

    def test_type_filter_narrows_to_away_only(self):
        client = Client()
        client.login(username="_test_club_viewer_b", password="pw")
        response = client.get("/operations/club-dashboard/schedule/", {"type": "away"})
        for row in response.context["rows"]:
            self.assertFalse(row["is_home"])

    def test_type_filter_never_leaks_another_clubs_matches(self):
        """Regression guard for the system-review note: whatever the filter
        UI looks like, the underlying queryset must stay scoped to this
        club's own matches - an unrelated club's fixture must never appear
        no matter which value ?type= is set to."""
        client = Client()
        client.login(username="_test_club_viewer_a", password="pw")
        for type_value in ("", "home", "away"):
            response = client.get("/operations/club-dashboard/schedule/", {"type": type_value})
            matches = [row["match"] for row in response.context["rows"]]
            self.assertNotIn(self.unrelated_match, matches)

    def test_type_filter_labels_are_clear_arabic_friendly_wording(self):
        """System review request: distinct, unambiguous Home/Away option
        text plus an inline explanation of what each side means - not the
        bare, easily-confused "Home"/"Away" words alone."""
        client = Client()
        client.login(username="_test_club_viewer_a", password="pw")
        response = client.get("/operations/club-dashboard/schedule/")
        self.assertContains(response, "All Matches")
        self.assertContains(response, "On Our Ground (Home)")
        self.assertContains(response, "Away From Our Ground")

    def test_view_link_carries_current_filter_as_back_param(self):
        client = Client()
        client.login(username="_test_club_viewer_a", password="pw")
        response = client.get("/operations/club-dashboard/schedule/", {"type": "home"})
        self.assertContains(response, "back=/operations/club-dashboard/schedule/%3Ftype%3Dhome")

    def test_match_detail_back_link_returns_to_the_filtered_list(self):
        """The whole point of the ?back= param: returning from a match
        detail page lands back on the schedule page with the same filter
        selected, not a plain reset to the homepage."""
        client = Client()
        client.login(username="_test_club_viewer_a", password="pw")
        back_target = "/operations/club-dashboard/schedule/?type=home"
        response = client.get(f"/operations/club-dashboard/matches/{self.match.pk}/", {"back": back_target})
        self.assertEqual(response.context["back_url"], back_target)
        self.assertContains(response, 'href="/operations/club-dashboard/schedule/?type=home"')

    def test_match_detail_rejects_an_unsafe_back_param(self):
        """A ?back= pointing off-site must never be trusted as a redirect
        target - falls back to the ordinary Club Dashboard home instead."""
        client = Client()
        client.login(username="_test_club_viewer_a", password="pw")
        response = client.get(
            f"/operations/club-dashboard/matches/{self.match.pk}/", {"back": "https://evil.example/"}
        )
        self.assertEqual(response.context["back_url"], "/operations/club-dashboard/")

    def test_status_choices_are_the_simplified_three_not_the_raw_cms_pipeline(self):
        """The club-facing Match Status filter only ever offers In
        Progress/Live/Finished - never the internal CMS pipeline stages
        (Draft/Ready for CMS/Sent to CMS/Published), which a club/
        coordinator on this page has no reason to know about."""
        client = Client()
        client.login(username="_test_club_viewer_a", password="pw")
        response = client.get("/operations/club-dashboard/schedule/")
        values = [value for value, _label in response.context["status_choices"]]
        self.assertEqual(values, ["in_progress", "live", "finished"])

    def test_status_filter_finished_only_shows_finished_matches(self):
        self.match.event_date = timezone.localtime().date() - timezone.timedelta(days=30)
        self.match.match_start_time = timezone.datetime.min.time()
        self.match.save(update_fields=["event_date", "match_start_time"])
        client = Client()
        client.login(username="_test_club_viewer_a", password="pw")
        response = client.get("/operations/club-dashboard/schedule/", {"status": "finished"})
        matches = [row["match"] for row in response.context["rows"]]
        self.assertIn(self.match, matches)

        response2 = client.get("/operations/club-dashboard/schedule/", {"status": "in_progress"})
        self.assertNotIn(self.match, [row["match"] for row in response2.context["rows"]])

    def test_page_uses_rtl_capable_base_shell(self):
        """Renders through operations/base.html, same shell (and its
        LANGUAGE_BIDI-driven dir=rtl/ltr) as every other page - no
        separate template system for this page."""
        client = Client()
        client.login(username="_test_club_viewer_a", password="pw")
        response = client.get("/operations/club-dashboard/")
        self.assertContains(response, "<html")
        self.assertContains(response, "toast-container")

    def test_sidebar_link_only_shown_to_club_viewer_now(self):
        """Product decision (2026-09-15): the sidebar's "Club Dashboard"
        link disappears for a Club Manager coordinator - only a real Club
        Viewer account keeps it."""
        client = Client()
        client.login(username="_test_club_viewer_a", password="pw")
        # Club Viewer is excluded from the Operations Dashboard itself
        # (ExcludeClubViewerAccessMixin) - check the sidebar on a page it
        # can actually reach.
        response = client.get("/operations/club-dashboard/")
        self.assertContains(response, "/operations/club-dashboard/")

        client2 = Client()
        client2.login(username="_test_club_a", password="pw")
        response2 = client2.get("/operations/")
        self.assertNotContains(response2, "/operations/club-dashboard/")

        client3 = Client()
        client3.login(username="_test_ops_manager", password="pw")
        response3 = client3.get("/operations/")
        self.assertNotContains(response3, "/operations/club-dashboard/")


class ClubViewerAccessRestrictionTests(TestCase):
    """The Operations Dashboard, the full Events/match list, and the
    Missing Requirements report are blocked entirely for accounts in the
    "Club Viewer" group - the real football-club audience, who have
    their own dedicated Club Dashboard instead. Release Schedule and
    Calendar stay open to everyone, Club Viewer included (see
    operations/views/release_schedule.py's own header comment and this
    session's explicit "التقويم كما هو الان" instruction).

    Deliberately a separate fixture from ClubDashboardPermissionsTestBase
    (whose users sit in "Club Manager", the internal-coordinator group)
    to prove the restriction is scoped to "Club Viewer" specifically and
    does not accidentally also catch "Club Manager" - that exact mix-up
    is what caused the incident this group split fixes (see commit
    c1bdee6 and its revert eb2bf61)."""

    @classmethod
    def setUpTestData(cls):
        club_viewer_group, _ = Group.objects.get_or_create(name="Club Viewer")
        cls.club_viewer_user = User.objects.create_user(username="_test_club_viewer", password="pw")
        cls.club_viewer_user.groups.add(club_viewer_group)
        Club.objects.create(name_ar="نادي متابعة", name_en="Follow Club", owner=cls.club_viewer_user)

        operations_manager_group, _ = Group.objects.get_or_create(name="Operations Manager")
        cls.ops_manager_user = User.objects.create_user(username="_test_ops_manager_cv", password="pw")
        cls.ops_manager_user.groups.add(operations_manager_group)

        club_manager_group, _ = Group.objects.get_or_create(name="Club Manager")
        cls.club_manager_user = User.objects.create_user(username="_test_club_manager_cv", password="pw")
        cls.club_manager_user.groups.add(club_manager_group)
        Club.objects.create(name_ar="نادي منسق", name_en="Coordinator Club", owner=cls.club_manager_user)

    def test_club_viewer_blocked_from_dashboard(self):
        client = Client()
        client.login(username="_test_club_viewer", password="pw")
        response = client.get("/operations/")
        self.assertEqual(response.status_code, 302)

    def test_club_viewer_blocked_from_match_list(self):
        client = Client()
        client.login(username="_test_club_viewer", password="pw")
        response = client.get("/operations/matches/")
        self.assertEqual(response.status_code, 302)

    def test_club_viewer_blocked_from_missing_requirements_report(self):
        client = Client()
        client.login(username="_test_club_viewer", password="pw")
        response = client.get("/operations/reports/missing-requirements/")
        self.assertEqual(response.status_code, 302)

    def test_club_viewer_not_blocked_from_release_schedule(self):
        client = Client()
        client.login(username="_test_club_viewer", password="pw")
        response = client.get("/operations/release-schedule/")
        self.assertEqual(response.status_code, 200)

    def test_club_viewer_not_blocked_from_calendar(self):
        client = Client()
        client.login(username="_test_club_viewer", password="pw")
        response = client.get("/operations/calendar/")
        self.assertEqual(response.status_code, 200)

    def test_club_viewer_not_blocked_from_own_club_dashboard(self):
        client = Client()
        client.login(username="_test_club_viewer", password="pw")
        response = client.get("/operations/club-dashboard/")
        self.assertEqual(response.status_code, 200)

    def test_club_manager_not_blocked_by_this_restriction(self):
        """Regression check - "Club Manager" (internal coordinators) must
        stay fully unaffected. This is the exact scenario the revert of
        commit c1bdee6 was about."""
        client = Client()
        client.login(username="_test_club_manager_cv", password="pw")
        for path in ("/operations/", "/operations/matches/", "/operations/reports/missing-requirements/"):
            response = client.get(path)
            self.assertEqual(response.status_code, 200, path)

    def test_operations_manager_not_blocked_by_this_restriction(self):
        client = Client()
        client.login(username="_test_ops_manager_cv", password="pw")
        for path in ("/operations/", "/operations/matches/", "/operations/reports/missing-requirements/"):
            response = client.get(path)
            self.assertEqual(response.status_code, 200, path)

    def test_login_redirects_club_viewer_to_club_dashboard(self):
        """Landing a Club Viewer on the (now-blocked) Operations Dashboard
        right after login would just bounce them straight back out - see
        HtmxLoginView.get_default_redirect_url."""
        client = Client()
        response = client.post("/login/", {"username": "_test_club_viewer", "password": "pw"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/operations/club-dashboard/")

    def test_login_with_a_stale_next_to_club_dashboard_does_not_loop_for_a_club_manager(self):
        """Regression test for a real ERR_TOO_MANY_REDIRECTS bug: a Club
        Manager coordinator (club_manager_cv here) hitting a stale
        ?next=/operations/club-dashboard/ link (from before the
        2026-09-15 product decision restricted that page to Club Viewer
        only) must NOT be sent there - that page raises PermissionDenied
        for them, and FriendlyPermissionDeniedMiddleware's HTTP_REFERER
        fallback would otherwise bounce them right back through this same
        login URL forever. HtmxLoginView.get_redirect_url() ignores the
        stale `next` in this specific case and falls back to the ordinary
        default redirect instead."""
        client = Client()
        response = client.post(
            "/login/?next=/operations/club-dashboard/",
            {"username": "_test_club_manager_cv", "password": "pw"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(response.url, "/operations/club-dashboard/")


class RiyalFilterTests(TestCase):
    """The {{ price|riyal }} template filter added for the 2026-09 system
    review's unified currency-format request - display formatting only,
    never touches the stored DecimalField value."""

    def test_whole_number_drops_trailing_zeros(self):
        from operations.templatetags.display_helpers import riyal

        self.assertEqual(riyal(Decimal("150.00")), "150 SAR")

    def test_real_fraction_is_kept(self):
        from operations.templatetags.display_helpers import riyal

        self.assertEqual(riyal(Decimal("150.50")), "150.50 SAR")

    def test_thousands_separator(self):
        from operations.templatetags.display_helpers import riyal

        self.assertEqual(riyal(Decimal("12500")), "12,500 SAR")

    def test_none_renders_as_an_em_dash_not_a_currency_unit_alone(self):
        from operations.templatetags.display_helpers import riyal

        self.assertEqual(riyal(None), "—")

    def test_arabic_language_shows_the_arabic_unit_word(self):
        from django.utils import translation

        from operations.templatetags.display_helpers import riyal

        with translation.override("ar"):
            self.assertEqual(riyal(Decimal("100")), "100 ريال")


class RefreshControlTests(ClubDashboardPermissionsTestBase):
    """The countdown/last-updated lines added next to the existing
    auto-refresh interval picker - both must exist in the markup (hidden
    by default; dashboard-refresh.js reveals them via JS) and reuse the
    same select/options rather than a second, competing control."""

    def test_countdown_and_last_updated_elements_present(self):
        client = Client()
        client.login(username="_test_ops_manager", password="pw")
        response = client.get("/operations/")
        self.assertContains(response, 'id="refresh-countdown"')
        self.assertContains(response, 'id="refresh-last-updated"')
        # Hidden by default - dashboard-refresh.js reveals them via JS once
        # it knows the stored interval, not the server.
        body = response.content.decode()
        countdown_tag = body[body.index('id="refresh-countdown"') - 200 : body.index('id="refresh-countdown"') + 250]
        self.assertIn("hidden", countdown_tag)

    def test_only_one_refresh_interval_select_on_the_page(self):
        client = Client()
        client.login(username="_test_ops_manager", password="pw")
        response = client.get("/operations/")
        self.assertEqual(response.content.decode().count('id="refresh-interval-select"'), 1)


class MatchCalendarTests(ClubDashboardPermissionsTestBase):
    """The single shared Match Calendar (operations:calendar) - covers the
    2026-09 system review's requests: a locale-aware month/today label
    (not the OS-locale strftime it used to be), a raised day-cell limit
    with no bare "+N more" hidden behind vague wording, and a text
    Home/Away badge for a club-scoped viewer (never shown to an Ops/SPL
    viewer, who has no "own club" to be home/away relative to)."""

    def _get(self, username, **params):
        client = Client()
        client.login(username=username, password="pw")
        return client.get("/operations/calendar/", params)

    def test_month_label_is_locale_aware_not_the_server_locale(self):
        """Regression test: the old strftime('%B %Y') always showed English
        month names regardless of site language, since strftime uses the
        OS/C locale, not Django's own translated month names. LocaleMiddleware
        reads the language from the django_language cookie, not from a
        translation.override() wrapped around the request - set it directly."""
        client = Client()
        client.login(username="_test_ops_manager", password="pw")
        client.cookies["django_language"] = "ar"
        response = client.get("/operations/calendar/", {"year": 2026, "month": 9})
        self.assertNotIn("September", response.content.decode())

    def test_today_label_present_in_context(self):
        response = self._get("_test_ops_manager")
        self.assertIn("today_label", response.context)
        self.assertTrue(response.context["today_label"])

    def test_coordinator_sees_home_away_badge_on_their_own_match(self):
        self.match.event_date = timezone.localtime().date()
        self.match.save(update_fields=["event_date"])
        response = self._get("_test_club_a", year=self.match.event_date.year, month=self.match.event_date.month)
        weeks = response.context["weeks"]
        cards = [card for week in weeks for day in week for card in day["matches"] if day["date"] == self.match.event_date]
        self.assertTrue(cards)
        self.assertTrue(cards[0]["is_home"])

    def test_away_side_coordinator_does_not_see_the_match_at_all(self):
        """This calendar deliberately keeps the OLD get_visible_matches
        scoping unchanged (per the system review's explicit instruction) -
        a coordinator only ever sees matches their own club HOSTS here,
        never one they're just visiting. So club_b (the away side of
        self.match) sees no card for it at all, not an is_home=False one -
        confirms Home/Away display was added without touching this
        existing visibility rule."""
        self.match.event_date = timezone.localtime().date()
        self.match.save(update_fields=["event_date"])
        response = self._get("_test_club_b", year=self.match.event_date.year, month=self.match.event_date.month)
        weeks = response.context["weeks"]
        cards = [card for week in weeks for day in week for card in day["matches"] if day["date"] == self.match.event_date]
        self.assertEqual(cards, [])

    def test_ops_manager_gets_no_home_away_badge(self):
        """An Ops/SPL viewer has no "own club" - is_home must be None so
        the template renders no side badge for them at all."""
        self.match.event_date = timezone.localtime().date()
        self.match.save(update_fields=["event_date"])
        response = self._get("_test_ops_manager", year=self.match.event_date.year, month=self.match.event_date.month)
        weeks = response.context["weeks"]
        cards = [card for week in weeks for day in week for card in day["matches"] if day["date"] == self.match.event_date]
        self.assertTrue(cards)
        self.assertIsNone(cards[0]["is_home"])

    def test_day_cell_shows_up_to_five_matches_directly(self):
        target_date = timezone.localtime().date()
        for i in range(7):
            Match.objects.create(
                competition=self.competition,
                home_club=self.club_a,
                away_club=self.club_b,
                slug=f"_test-calendar-extra-{i}",
                title_ar=f"مباراة {i}",
                title_en=f"Extra Match {i}",
                event_date=target_date,
            )
        response = self._get("_test_ops_manager", year=target_date.year, month=target_date.month)
        weeks = response.context["weeks"]
        day = next(d for week in weeks for d in week if d["date"] == target_date)
        self.assertEqual(len(day["matches"]), 5)
        self.assertEqual(day["extra_count"], 2)

    def test_more_matches_button_names_matches_not_a_bare_more_link(self):
        target_date = timezone.localtime().date()
        for i in range(7):
            Match.objects.create(
                competition=self.competition,
                home_club=self.club_a,
                away_club=self.club_b,
                slug=f"_test-calendar-wording-{i}",
                title_ar=f"مباراة {i}",
                title_en=f"Extra Match {i}",
                event_date=target_date,
            )
        response = self._get("_test_ops_manager", year=target_date.year, month=target_date.month)
        self.assertContains(response, "more matches")
        self.assertContains(response, "View all of this day's matches")


# --- Phase 4: Club Pricing Plan tests -------------------------------------


def _pdf_file(name="plan.pdf", size=None):
    content = b"%PDF-1.4 fake plan content"
    if size is not None:
        content += b"0" * size
    return SimpleUploadedFile(name, content, content_type="application/pdf")


class IsolatedMediaMixin:
    """Any test that actually saves a ClubPricingPlan writes a real file to
    disk via FileField storage - that write is NOT part of TestCase's
    per-test DB transaction, so a rolled-back test still leaves the file
    behind in MEDIA_ROOT. Redirects MEDIA_ROOT to a throwaway temp
    directory for the life of the class and deletes it afterward, so
    these tests never touch the project's real media/ folder."""

    @classmethod
    def setUpClass(cls):
        cls._media_root = tempfile.mkdtemp(prefix="_test_media_")
        cls._media_override = override_settings(MEDIA_ROOT=cls._media_root)
        cls._media_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._media_override.disable()
        shutil.rmtree(cls._media_root, ignore_errors=True)


class ClubPricingPlanModelTests(IsolatedMediaMixin, ClubDashboardPermissionsTestBase):
    def test_create_plan_linked_to_match_and_club(self):
        plan = ClubPricingPlan.objects.create(
            match=self.match, club=self.club_a, file=_pdf_file(), version=1, uploaded_by=self.user_a,
        )
        self.assertEqual(plan.match, self.match)
        self.assertEqual(plan.club, self.club_a)
        self.assertEqual(plan.uploaded_by, self.user_a)

    def test_initial_status_is_uploaded(self):
        plan = ClubPricingPlan.objects.create(match=self.match, club=self.club_a, file=_pdf_file(), version=1)
        self.assertEqual(plan.status, ClubPricingPlan.Status.UPLOADED)

    def test_version_is_saved_as_given(self):
        plan = ClubPricingPlan.objects.create(match=self.match, club=self.club_a, file=_pdf_file(), version=3)
        self.assertEqual(plan.version, 3)

    def test_duplicate_version_for_same_match_is_rejected(self):
        ClubPricingPlan.objects.create(match=self.match, club=self.club_a, file=_pdf_file(), version=1)
        with self.assertRaises(Exception):
            ClubPricingPlan.objects.create(match=self.match, club=self.club_a, file=_pdf_file(), version=1)

    def test_uploading_a_plan_does_not_touch_spl_or_cms_fields(self):
        """The one rule this whole phase exists to protect."""
        self.match.ticketing_plan_approved = False
        self.match.spl_tickets_sent = False
        self.match.cms_status = Match.Status.DRAFT
        self.match.save()

        ClubPricingPlan.objects.create(match=self.match, club=self.club_a, file=_pdf_file(), version=1)

        self.match.refresh_from_db()
        self.assertFalse(self.match.ticketing_plan_approved)
        self.assertFalse(self.match.spl_tickets_sent)
        self.assertEqual(self.match.cms_status, Match.Status.DRAFT)
        self.assertFalse(self.match.plan_approval_file)


class ClubPricingPlanUploadHomeClubTests(IsolatedMediaMixin, ClubDashboardPermissionsTestBase):
    def test_home_club_can_open_upload_page(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get(f"/operations/club-dashboard/matches/{self.match.pk}/pricing-plan/upload/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "operations/club_pricing_plan_upload.html")

    def test_percentage_asked_once_as_two_home_away_boxes_not_a_file_field(self):
        """Regression test: the manual-entry form's optional file-attach
        field was removed (redundant with category pricing/Excel import),
        and the Home/Away split is asked once as two labeled boxes
        (Home %/Away %) rather than a single ambiguous percentage field,
        never duplicated across the two submission forms on this page."""
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get(f"/operations/club-dashboard/matches/{self.match.pk}/pricing-plan/upload/")
        self.assertNotContains(response, "Attach a supporting document")
        self.assertContains(response, "Home %")
        self.assertContains(response, "Away %")
        self.assertEqual(response.content.decode().count('id="id_home_percentage"'), 1)

    def test_home_club_can_upload_a_plan(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.post(
            f"/operations/club-dashboard/matches/{self.match.pk}/pricing-plan/upload/",
            {"file": _pdf_file(), "home_percentage": 70},
        )
        self.assertRedirects(
            response, f"/operations/club-dashboard/matches/{self.match.pk}/", fetch_redirect_response=False
        )
        plan = ClubPricingPlan.objects.get(match=self.match)
        self.assertEqual(plan.club, self.club_a)
        self.assertEqual(plan.version, 1)

    def test_uploaded_by_is_the_logged_in_user_not_request_data(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        client.post(
            f"/operations/club-dashboard/matches/{self.match.pk}/pricing-plan/upload/",
            {"file": _pdf_file(), "home_percentage": 70, "uploaded_by": self.user_b.pk},
        )
        plan = ClubPricingPlan.objects.get(match=self.match)
        self.assertEqual(plan.uploaded_by, self.user_a)

    def test_club_cannot_upload_on_behalf_of_another_club(self):
        """The form has no club field at all - club is always
        match.home_club, regardless of what's posted."""
        client = Client()
        client.login(username="_test_club_a", password="pw")
        client.post(
            f"/operations/club-dashboard/matches/{self.match.pk}/pricing-plan/upload/",
            {"file": _pdf_file(), "home_percentage": 70, "club": self.club_c.pk, "club_id": self.club_c.pk},
        )
        plan = ClubPricingPlan.objects.get(match=self.match)
        self.assertEqual(plan.club, self.club_a)

    def test_second_upload_creates_version_two(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        client.post(
            f"/operations/club-dashboard/matches/{self.match.pk}/pricing-plan/upload/", {"file": _pdf_file(), "home_percentage": 70},
        )
        client.post(
            f"/operations/club-dashboard/matches/{self.match.pk}/pricing-plan/upload/", {"file": _pdf_file(), "home_percentage": 70},
        )
        self.assertEqual(ClubPricingPlan.objects.filter(match=self.match).count(), 2)
        latest = ClubPricingPlan.objects.filter(match=self.match).order_by("-version").first()
        self.assertEqual(latest.version, 2)

    def test_activity_log_recorded_on_upload(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        client.post(
            f"/operations/club-dashboard/matches/{self.match.pk}/pricing-plan/upload/", {"file": _pdf_file(), "home_percentage": 70},
        )
        self.assertTrue(
            self.match.activity_logs.filter(description__icontains="pricing plan uploaded").exists()
        )

    def test_success_message_shown(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.post(
            f"/operations/club-dashboard/matches/{self.match.pk}/pricing-plan/upload/",
            {"file": _pdf_file(), "home_percentage": 70},
            follow=True,
        )
        messages = list(response.context["messages"])
        self.assertTrue(any("uploaded" in str(m) for m in messages))

    def test_spl_and_cms_fields_unchanged_after_real_upload_request(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        client.post(
            f"/operations/club-dashboard/matches/{self.match.pk}/pricing-plan/upload/", {"file": _pdf_file(), "home_percentage": 70},
        )
        self.match.refresh_from_db()
        self.assertFalse(self.match.ticketing_plan_approved)
        self.assertFalse(self.match.spl_tickets_sent)
        self.assertFalse(self.match.plan_approval_file)

    def test_rejects_disallowed_file_type(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        bad_file = SimpleUploadedFile("plan.exe", b"not a real plan", content_type="application/octet-stream")
        client.post(
            f"/operations/club-dashboard/matches/{self.match.pk}/pricing-plan/upload/", {"file": bad_file, "home_percentage": 70},
        )
        self.assertFalse(ClubPricingPlan.objects.filter(match=self.match).exists())

    def test_rejects_oversized_file(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        oversized = _pdf_file(size=11 * 1024 * 1024)
        client.post(
            f"/operations/club-dashboard/matches/{self.match.pk}/pricing-plan/upload/", {"file": oversized, "home_percentage": 70},
        )
        self.assertFalse(ClubPricingPlan.objects.filter(match=self.match).exists())

    def test_cannot_upload_once_spl_has_approved(self):
        self.match.ticketing_plan_approved = True
        self.match.save(update_fields=["ticketing_plan_approved"])
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get(f"/operations/club-dashboard/matches/{self.match.pk}/pricing-plan/upload/")
        self.assertEqual(response.status_code, 302)

    def test_home_percentage_is_required_to_save_a_plan(self):
        """The club's own Home/Away split - required for every new plan
        since it varies club by club and SPL needs it with the seat map."""
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.post(
            f"/operations/club-dashboard/matches/{self.match.pk}/pricing-plan/upload/", {"file": _pdf_file()},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ClubPricingPlan.objects.filter(match=self.match).exists())

    def test_home_percentage_must_be_within_0_and_100(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.post(
            f"/operations/club-dashboard/matches/{self.match.pk}/pricing-plan/upload/",
            {"file": _pdf_file(), "home_percentage": 150},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ClubPricingPlan.objects.filter(match=self.match).exists())

    def test_home_percentage_is_saved_and_away_is_derived(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        client.post(
            f"/operations/club-dashboard/matches/{self.match.pk}/pricing-plan/upload/",
            {"file": _pdf_file(), "home_percentage": 70},
        )
        plan = ClubPricingPlan.objects.get(match=self.match)
        self.assertEqual(plan.home_percentage, 70)
        self.assertEqual(plan.away_percentage, 30)

    def test_home_percentage_required_for_excel_import_too(self):
        import io

        import openpyxl

        category = VenueSeatingCategory.objects.create(
            venue=self.match.venue, club=self.club_a, code="_TEST XLSX CAT",
        ) if self.match.venue_id else None
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["code", "price"])
        if category:
            ws.append([category.code, 100])
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        client = Client()
        client.login(username="_test_club_a", password="pw")
        client.post(
            f"/operations/club-dashboard/matches/{self.match.pk}/pricing-plan/import/",
            {"import_file": SimpleUploadedFile("prices.xlsx", buffer.read())},
        )
        self.assertFalse(ClubPricingPlan.objects.filter(match=self.match).exists())

    def test_shared_venue_only_shows_this_clubs_own_positioned_image(self):
        """Regression test: two clubs at the same physical venue (e.g. Al
        Kholood and Al Hazm both at Al Hazm Stadium), each with their own
        overview photo - the upload page must only ever show the image
        THIS club's own categories are positioned on, never the other
        club's image just because they share a Venue row."""
        from matches.models import MapPlacement, Venue, VenueImage

        self.match.venue = Venue.objects.create(name_ar="_ملعب مشترك", name_en="_Shared Venue")
        self.match.save(update_fields=["venue"])

        own_image = VenueImage.objects.create(venue=self.match.venue, caption="_own image", image=_tiny_png())
        other_clubs_image = VenueImage.objects.create(
            venue=self.match.venue, caption="_other club image", image=_tiny_png(),
        )

        own_category = VenueSeatingCategory.objects.create(
            venue=self.match.venue, club=self.club_a, code="_TEST OWN CAT",
        )
        MapPlacement.objects.create(
            venue=self.match.venue, club=self.club_a, position_image=own_image,
            category=own_category, position_x=10, position_y=10,
        )
        # club_c has no relation to this match at all - stands in for the
        # other club sharing the venue.
        other_category = VenueSeatingCategory.objects.create(
            venue=self.match.venue, club=self.club_c, code="_TEST OTHER CAT",
        )
        MapPlacement.objects.create(
            venue=self.match.venue, club=self.club_c, position_image=other_clubs_image,
            category=other_category, position_x=20, position_y=20,
        )

        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get(f"/operations/club-dashboard/matches/{self.match.pk}/pricing-plan/upload/")
        venue_images = list(response.context["venue_images"])
        self.assertEqual(venue_images, [own_image])

    def test_no_venue_image_shown_before_this_clubs_categories_are_positioned(self):
        """Safer than showing every image on a shared venue at random:
        nothing is shown until this club's own categories have a saved
        position, even if other images already exist for the venue."""
        from matches.models import Venue, VenueImage

        self.match.venue = Venue.objects.create(name_ar="_ملعب مشترك ٢", name_en="_Shared Venue 2")
        self.match.save(update_fields=["venue"])
        VenueImage.objects.create(venue=self.match.venue, caption="_unrelated image")
        VenueSeatingCategory.objects.create(venue=self.match.venue, club=self.club_a, code="_TEST UNPOSITIONED CAT")

        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get(f"/operations/club-dashboard/matches/{self.match.pk}/pricing-plan/upload/")
        self.assertEqual(list(response.context["venue_images"]), [])

    def test_home_club_can_download_the_price_template(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get(f"/operations/club-dashboard/matches/{self.match.pk}/pricing-plan/template/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def test_away_club_cannot_download_the_price_template(self):
        client = Client()
        client.login(username="_test_club_b", password="pw")
        response = client.get(f"/operations/club-dashboard/matches/{self.match.pk}/pricing-plan/template/")
        self.assertEqual(response.status_code, 302)


class ClubPricingPlanAwayClubTests(IsolatedMediaMixin, ClubDashboardPermissionsTestBase):
    def setUp(self):
        self.plan = ClubPricingPlan.objects.create(
            match=self.match, club=self.club_a, file=_pdf_file(), version=1, uploaded_by=self.user_a,
        )

    def test_away_club_sees_match_but_no_upload_button(self):
        client = Client()
        client.login(username="_test_club_b", password="pw")
        response = client.get(f"/operations/club-dashboard/matches/{self.match.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'operations:club-pricing-plan-upload')
        self.assertNotContains(response, "/pricing-plan/upload/")

    def test_away_club_direct_get_to_upload_page_denied(self):
        client = Client()
        client.login(username="_test_club_b", password="pw")
        response = client.get(f"/operations/club-dashboard/matches/{self.match.pk}/pricing-plan/upload/")
        self.assertEqual(response.status_code, 302)

    def test_away_club_direct_post_to_upload_denied(self):
        client = Client()
        client.login(username="_test_club_b", password="pw")
        response = client.post(
            f"/operations/club-dashboard/matches/{self.match.pk}/pricing-plan/upload/", {"file": _pdf_file(), "home_percentage": 70},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ClubPricingPlan.objects.filter(match=self.match).count(), 1)

    def test_away_club_cannot_upload_a_plan_on_unrelated_match(self):
        client = Client()
        client.login(username="_test_club_b", password="pw")
        response = client.post(
            f"/operations/club-dashboard/matches/{self.unrelated_match.pk}/pricing-plan/upload/",
            {"file": _pdf_file(), "home_percentage": 70},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ClubPricingPlan.objects.filter(match=self.unrelated_match).exists())

    def test_away_club_cannot_download_home_clubs_file(self):
        client = Client()
        client.login(username="_test_club_b", password="pw")
        response = client.get(f"/operations/club-dashboard/pricing-plan/{self.plan.pk}/download/")
        self.assertEqual(response.status_code, 302)

    def test_home_club_can_download_its_own_file(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get(f"/operations/club-dashboard/pricing-plan/{self.plan.pk}/download/")
        self.assertEqual(response.status_code, 200)

    def test_unrelated_club_cannot_download_file_by_guessing_id(self):
        client = Client()
        client.login(username="_test_club_c", password="pw")
        response = client.get(f"/operations/club-dashboard/pricing-plan/{self.plan.pk}/download/")
        self.assertEqual(response.status_code, 302)


class ClubPricingPlanOtherUsersTests(ClubDashboardPermissionsTestBase):
    def test_user_with_no_club_cannot_upload(self):
        client = Client()
        client.login(username="_test_ops_manager", password="pw")
        response = client.get(f"/operations/club-dashboard/matches/{self.match.pk}/pricing-plan/upload/")
        self.assertEqual(response.status_code, 302)

    def test_viewer_cannot_upload_without_being_a_club(self):
        """Viewer owns no club - can_manage_home_match is False for them
        regardless of their Viewer group membership, which grants no
        club-side upload capability."""
        client = Client()
        client.login(username="_test_viewer", password="pw")
        response = client.get(f"/operations/club-dashboard/matches/{self.match.pk}/pricing-plan/upload/")
        self.assertEqual(response.status_code, 302)

    def test_operations_dashboard_unaffected_by_new_model(self):
        client = Client()
        client.login(username="_test_ops_manager", password="pw")
        response = client.get("/operations/")
        self.assertEqual(response.status_code, 200)

    def test_spl_approval_flow_unaffected_by_new_model(self):
        client = Client()
        client.login(username="_test_viewer", password="pw")
        response = client.get("/operations/reports/spl/approvals/")
        self.assertEqual(response.status_code, 200)


# --- Phase 5: submit-to-SPL / confirm-submission tests --------------------


class ClubPricingPlanSubmitTests(IsolatedMediaMixin, ClubDashboardPermissionsTestBase):
    def setUp(self):
        self.plan = ClubPricingPlan.objects.create(
            match=self.match, club=self.club_a, file=_pdf_file(), version=1, uploaded_by=self.user_a,
        )

    def test_home_club_can_open_submit_page_when_uploaded(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get(f"/operations/club-dashboard/pricing-plan/{self.plan.pk}/submit/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "operations/club_pricing_plan_submit.html")

    def test_home_club_can_submit(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.post(f"/operations/club-dashboard/pricing-plan/{self.plan.pk}/submit/")
        self.assertRedirects(
            response, f"/operations/club-dashboard/matches/{self.match.pk}/", fetch_redirect_response=False
        )
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.status, ClubPricingPlan.Status.SUBMITTED_TO_SPL)
        self.assertEqual(self.plan.submitted_by, self.user_a)
        self.assertIsNotNone(self.plan.submitted_at)

    def test_away_club_cannot_submit(self):
        client = Client()
        client.login(username="_test_club_b", password="pw")
        response = client.post(f"/operations/club-dashboard/pricing-plan/{self.plan.pk}/submit/")
        self.assertEqual(response.status_code, 302)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.status, ClubPricingPlan.Status.UPLOADED)

    def test_user_with_no_club_cannot_submit(self):
        client = Client()
        client.login(username="_test_ops_manager", password="pw")
        response = client.post(f"/operations/club-dashboard/pricing-plan/{self.plan.pk}/submit/")
        self.assertEqual(response.status_code, 302)

    def test_cannot_submit_without_a_plan(self):
        """No plan exists at all for this second match - can_submit_home_match_to_spl
        must be False, not crash."""
        second_match = Match.objects.create(
            competition=self.competition, home_club=self.club_a, away_club=self.club_c,
            slug="_test-second-match", title_ar="مباراة ثانية", title_en="Second Match",
        )
        self.assertFalse(can_submit_home_match_to_spl(self.user_a, second_match))

    def test_cannot_submit_an_old_version(self):
        newer = ClubPricingPlan.objects.create(match=self.match, club=self.club_a, file=_pdf_file(), version=2)
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.post(f"/operations/club-dashboard/pricing-plan/{self.plan.pk}/submit/")
        self.assertEqual(response.status_code, 302)
        self.plan.refresh_from_db()
        newer.refresh_from_db()
        self.assertEqual(self.plan.status, ClubPricingPlan.Status.UPLOADED)
        self.assertEqual(newer.status, ClubPricingPlan.Status.UPLOADED)

    def test_cannot_submit_twice(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        client.post(f"/operations/club-dashboard/pricing-plan/{self.plan.pk}/submit/")
        first_submitted_at = ClubPricingPlan.objects.get(pk=self.plan.pk).submitted_at

        response = client.post(f"/operations/club-dashboard/pricing-plan/{self.plan.pk}/submit/")
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.submitted_at, first_submitted_at)
        self.assertEqual(self.match.activity_logs.filter(description__icontains="submitted pricing plan").count(), 1)

    def test_submission_does_not_touch_spl_or_cms_fields(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        client.post(f"/operations/club-dashboard/pricing-plan/{self.plan.pk}/submit/")
        self.match.refresh_from_db()
        self.assertFalse(self.match.ticketing_plan_approved)
        self.assertFalse(self.match.spl_tickets_sent)
        self.assertFalse(self.match.plan_approval_file)

    def test_activity_log_recorded_on_submit(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        client.post(f"/operations/club-dashboard/pricing-plan/{self.plan.pk}/submit/")
        self.assertTrue(self.match.activity_logs.filter(description__icontains="submitted pricing plan").exists())


class ClubPricingPlanConfirmSubmissionTests(IsolatedMediaMixin, ClubDashboardPermissionsTestBase):
    def setUp(self):
        self.plan = ClubPricingPlan.objects.create(
            match=self.match, club=self.club_a, file=_pdf_file(), version=1, uploaded_by=self.user_a,
        )

    def test_confirm_button_not_available_before_submission(self):
        self.assertFalse(can_confirm_home_match_submission(self.user_a, self.match))
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get(f"/operations/club-dashboard/matches/{self.match.pk}/")
        self.assertNotContains(response, "confirm-submission")

    def test_cannot_confirm_before_submitting(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.post(f"/operations/club-dashboard/pricing-plan/{self.plan.pk}/confirm-submission/")
        self.assertEqual(response.status_code, 302)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.status, ClubPricingPlan.Status.UPLOADED)

    def _submit(self):
        self.plan.status = ClubPricingPlan.Status.SUBMITTED_TO_SPL
        self.plan.submitted_at = timezone.now()
        self.plan.submitted_by = self.user_a
        self.plan.save()

    def test_home_club_can_confirm_after_submission(self):
        self._submit()
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.post(f"/operations/club-dashboard/pricing-plan/{self.plan.pk}/confirm-submission/")
        self.assertRedirects(
            response, f"/operations/club-dashboard/matches/{self.match.pk}/", fetch_redirect_response=False
        )
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.status, ClubPricingPlan.Status.SUBMISSION_CONFIRMED)
        self.assertEqual(self.plan.confirmed_by, self.user_a)
        self.assertIsNotNone(self.plan.confirmed_at)

    def test_away_club_cannot_confirm(self):
        self._submit()
        client = Client()
        client.login(username="_test_club_b", password="pw")
        response = client.post(f"/operations/club-dashboard/pricing-plan/{self.plan.pk}/confirm-submission/")
        self.assertEqual(response.status_code, 302)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.status, ClubPricingPlan.Status.SUBMITTED_TO_SPL)

    def test_cannot_confirm_twice(self):
        self._submit()
        client = Client()
        client.login(username="_test_club_a", password="pw")
        client.post(f"/operations/club-dashboard/pricing-plan/{self.plan.pk}/confirm-submission/")
        first_confirmed_at = ClubPricingPlan.objects.get(pk=self.plan.pk).confirmed_at

        client.post(f"/operations/club-dashboard/pricing-plan/{self.plan.pk}/confirm-submission/")
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.confirmed_at, first_confirmed_at)
        self.assertEqual(self.match.activity_logs.filter(description__icontains="confirmed pricing plan").count(), 1)

    def test_direct_post_on_another_matchs_plan_by_non_owner_denied(self):
        other_match = Match.objects.create(
            competition=self.competition, home_club=self.club_c, away_club=self.club_a,
            slug="_test-c-vs-a", title_ar="ج ضد أ", title_en="C vs A",
        )
        other_plan = ClubPricingPlan.objects.create(
            match=other_match, club=self.club_c, file=_pdf_file(), version=1,
            status=ClubPricingPlan.Status.SUBMITTED_TO_SPL, submitted_at=timezone.now(),
        )
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.post(f"/operations/club-dashboard/pricing-plan/{other_plan.pk}/confirm-submission/")
        self.assertEqual(response.status_code, 302)
        other_plan.refresh_from_db()
        self.assertEqual(other_plan.status, ClubPricingPlan.Status.SUBMITTED_TO_SPL)

    def test_confirmation_does_not_touch_spl_or_cms_fields(self):
        cms_status_before = self.match.cms_status
        self._submit()
        client = Client()
        client.login(username="_test_club_a", password="pw")
        client.post(f"/operations/club-dashboard/pricing-plan/{self.plan.pk}/confirm-submission/")
        self.match.refresh_from_db()
        self.assertFalse(self.match.ticketing_plan_approved)
        self.assertFalse(self.match.spl_tickets_sent)
        self.assertEqual(self.match.cms_status, cms_status_before)

    def test_activity_log_recorded_on_confirm(self):
        self._submit()
        client = Client()
        client.login(username="_test_club_a", password="pw")
        client.post(f"/operations/club-dashboard/pricing-plan/{self.plan.pk}/confirm-submission/")
        self.assertTrue(self.match.activity_logs.filter(description__icontains="confirmed pricing plan").exists())


class SPLPricingPlanDecisionTests(ClubDashboardPermissionsTestBase):
    """Covers the SPL Approvals page's approve/reject decision flow: state
    transitions, idempotency on a double POST, activity log, and the
    notification sent to the home club (see spl/views/pricing_plan_decision.py
    and notifications.services.notify_club)."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # SPLApprovalsView/SPLReportFilterMixin hard-scope every row on this
        # page to the Roshan League competition (seeded for every database,
        # test included, by matches/migrations/0006_backfill_roshan_league.py)
        # - the base fixture's own "Test League" competition never appears on
        # this page at all, so tests that need a visible row must use this one.
        from operations.views.helpers import get_roshan_league_competition
        roshan = get_roshan_league_competition()
        cls.match.competition = roshan
        cls.match.save(update_fields=["competition"])

        cls.category = None
        if cls.match.venue_id:
            cls.category = VenueSeatingCategory.objects.create(
                venue=cls.match.venue, club=cls.club_a, code="_TEST CAT",
            )
        cls.plan = ClubPricingPlan.objects.create(
            match=cls.match, club=cls.club_a, version=1,
            status=ClubPricingPlan.Status.SUBMITTED_TO_SPL,
        )
        if cls.category:
            ClubPricingPlanCategoryPrice.objects.create(plan=cls.plan, category=cls.category, price=150)

    def _approve(self, username="_test_ops_manager"):
        client = Client()
        client.login(username=username, password="pw")
        return client, client.post(f"/operations/pricing-plan/{self.plan.pk}/spl-approve/")

    def _reject(self, note="Needs corrected pricing.", username="_test_ops_manager"):
        client = Client()
        client.login(username=username, password="pw")
        data = {"note": note} if note is not None else {}
        return client, client.post(f"/operations/pricing-plan/{self.plan.pk}/spl-reject/", data)

    def test_approve_sets_decision_user_and_timestamp(self):
        client, response = self._approve()
        self.assertEqual(response.status_code, 302)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.spl_decision, ClubPricingPlan.SPLDecision.APPROVED)
        self.assertEqual(self.plan.spl_decision_by.username, "_test_ops_manager")
        self.assertIsNotNone(self.plan.spl_decision_at)

    def test_approve_syncs_match_ticketing_plan_approved_only(self):
        cms_status_before = self.match.cms_status
        self._approve()
        self.match.refresh_from_db()
        self.assertTrue(self.match.ticketing_plan_approved)
        self.assertIsNotNone(self.match.ticketing_plan_approved_at)
        self.assertEqual(self.match.cms_status, cms_status_before)

    def test_approve_creates_activity_log(self):
        self._approve()
        self.assertTrue(
            self.match.activity_logs.filter(description__icontains=f"approved pricing plan v{self.plan.version}").exists()
        )

    def test_approve_notifies_home_club_owner(self):
        self._approve()
        notification = Notification.objects.filter(
            recipient=self.user_a, notification_type="pricing_plan_approved", plan=self.plan,
        ).first()
        self.assertIsNotNone(notification)
        self.assertIn(str(self.match), notification.message)
        self.assertEqual(notification.match_id, self.match.pk)

    def test_approve_does_not_notify_away_club(self):
        self._approve()
        self.assertFalse(
            Notification.objects.filter(recipient=self.user_b, notification_type="pricing_plan_approved").exists()
        )

    def test_double_submit_approve_does_not_duplicate_log_or_notification(self):
        self._approve()
        self._approve()
        self.assertEqual(
            self.match.activity_logs.filter(description__icontains="approved pricing plan").count(), 1
        )
        self.assertEqual(
            Notification.objects.filter(recipient=self.user_a, notification_type="pricing_plan_approved").count(), 1
        )

    def test_cannot_approve_already_rejected_plan(self):
        self._reject()
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.spl_decision, ClubPricingPlan.SPLDecision.REJECTED)
        self._approve()
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.spl_decision, ClubPricingPlan.SPLDecision.REJECTED)

    def test_reject_requires_a_note(self):
        client, response = self._reject(note="")
        self.assertEqual(response.status_code, 302)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.spl_decision, ClubPricingPlan.SPLDecision.PENDING)

    def test_reject_saves_the_exact_note_entered(self):
        self._reject(note="Prices for CAT 1 look wrong.")
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.spl_decision, ClubPricingPlan.SPLDecision.REJECTED)
        self.assertEqual(self.plan.spl_decision_note, "Prices for CAT 1 look wrong.")

    def test_reject_creates_activity_log_with_note(self):
        self._reject(note="Prices for CAT 1 look wrong.")
        self.assertTrue(
            self.match.activity_logs.filter(description__icontains="Prices for CAT 1 look wrong.").exists()
        )

    def test_reject_notifies_home_club_with_reason(self):
        self._reject(note="Prices for CAT 1 look wrong.")
        notification = Notification.objects.filter(
            recipient=self.user_a, notification_type="pricing_plan_rejected", plan=self.plan,
        ).first()
        self.assertIsNotNone(notification)
        self.assertIn("Prices for CAT 1 look wrong.", notification.message)

    def test_double_submit_reject_does_not_duplicate_log_or_notification(self):
        self._reject(note="First reason.")
        self._reject(note="Second reason.")
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.spl_decision_note, "First reason.")
        self.assertEqual(
            Notification.objects.filter(recipient=self.user_a, notification_type="pricing_plan_rejected").count(), 1
        )

    def test_reject_syncs_ticketing_plan_approved_false(self):
        self.match.ticketing_plan_approved = True
        self.match.save(update_fields=["ticketing_plan_approved"])
        self._reject()
        self.match.refresh_from_db()
        self.assertFalse(self.match.ticketing_plan_approved)

    def test_club_user_cannot_approve_directly(self):
        client, response = self._approve(username="_test_club_a")
        self.assertEqual(response.status_code, 302)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.spl_decision, ClubPricingPlan.SPLDecision.PENDING)

    def test_club_user_cannot_reject_directly(self):
        client, response = self._reject(username="_test_club_a")
        self.assertEqual(response.status_code, 302)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.spl_decision, ClubPricingPlan.SPLDecision.PENDING)

    def test_viewer_can_approve(self):
        client, response = self._approve(username="_test_viewer")
        self.assertEqual(response.status_code, 302)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.spl_decision, ClubPricingPlan.SPLDecision.APPROVED)

    def test_cannot_decide_on_a_superseded_plan_version(self):
        newer = ClubPricingPlan.objects.create(
            match=self.match, club=self.club_a, version=2, status=ClubPricingPlan.Status.UPLOADED,
        )
        client, response = self._approve()
        self.assertEqual(response.status_code, 302)
        self.plan.refresh_from_db()
        newer.refresh_from_db()
        self.assertEqual(self.plan.spl_decision, ClubPricingPlan.SPLDecision.PENDING)
        self.assertEqual(newer.spl_decision, ClubPricingPlan.SPLDecision.PENDING)


class ClubPricingPlanAdminActionsTests(ClubDashboardPermissionsTestBase):
    """The Django Admin's "Approve selected pricing plans" / "Reject
    selected pricing plans" actions on ClubPricingPlanAdmin - the same
    business logic as SPLPricingPlanDecisionTests above (state transitions,
    idempotency, activity log, notification), reached from /admin/ instead."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.category = None
        if cls.match.venue_id:
            cls.category = VenueSeatingCategory.objects.create(
                venue=cls.match.venue, club=cls.club_a, code="_TEST ADMIN CAT",
            )
        cls.plan = ClubPricingPlan.objects.create(
            match=cls.match, club=cls.club_a, version=1,
            status=ClubPricingPlan.Status.SUBMITTED_TO_SPL,
        )
        if cls.category:
            ClubPricingPlanCategoryPrice.objects.create(plan=cls.plan, category=cls.category, price=150)

    def _admin_client(self):
        client = Client()
        client.login(username="_test_super", password="pw")
        return client

    def test_venue_image_registered_in_admin(self):
        response = self._admin_client().get("/admin/matches/venueimage/")
        self.assertEqual(response.status_code, 200)

    def test_venue_seating_category_registered_in_admin(self):
        response = self._admin_client().get("/admin/matches/venueseatingcategory/")
        self.assertEqual(response.status_code, 200)

    def test_approve_action_via_admin(self):
        client = self._admin_client()
        response = client.post("/admin/operations/clubpricingplan/", {
            "action": "approve_pricing_plans",
            "_selected_action": [str(self.plan.pk)],
        })
        self.assertEqual(response.status_code, 302)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.spl_decision, ClubPricingPlan.SPLDecision.APPROVED)
        self.assertEqual(self.plan.spl_decision_by.username, "_test_super")

        self.match.refresh_from_db()
        self.assertTrue(self.match.ticketing_plan_approved)
        self.assertTrue(
            self.match.activity_logs.filter(description__icontains=f"approved pricing plan v{self.plan.version}").exists()
        )
        self.assertTrue(
            Notification.objects.filter(recipient=self.user_a, notification_type="pricing_plan_approved", plan=self.plan).exists()
        )

    def test_reject_action_via_admin_shows_a_note_form_first(self):
        client = self._admin_client()
        response = client.post("/admin/operations/clubpricingplan/", {
            "action": "reject_pricing_plans",
            "_selected_action": [str(self.plan.pk)],
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reject pricing plans")
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.spl_decision, ClubPricingPlan.SPLDecision.PENDING)

    def test_reject_action_via_admin_applies_the_note(self):
        client = self._admin_client()
        response = client.post("/admin/operations/clubpricingplan/", {
            "action": "reject_pricing_plans",
            "_selected_action": [str(self.plan.pk)],
            "apply": "1",
            "note": "Prices for CAT 1 look wrong.",
        })
        self.assertEqual(response.status_code, 302)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.spl_decision, ClubPricingPlan.SPLDecision.REJECTED)
        self.assertEqual(self.plan.spl_decision_note, "Prices for CAT 1 look wrong.")

        self.match.refresh_from_db()
        self.assertFalse(self.match.ticketing_plan_approved)
        self.assertTrue(
            Notification.objects.filter(recipient=self.user_a, notification_type="pricing_plan_rejected", plan=self.plan).exists()
        )

    def test_approve_action_skips_an_already_decided_plan(self):
        self.plan.spl_decision = ClubPricingPlan.SPLDecision.REJECTED
        self.plan.save(update_fields=["spl_decision"])
        client = self._admin_client()
        client.post("/admin/operations/clubpricingplan/", {
            "action": "approve_pricing_plans",
            "_selected_action": [str(self.plan.pk)],
        })
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.spl_decision, ClubPricingPlan.SPLDecision.REJECTED)


class SPLApprovalsPageDecisionUITests(ClubDashboardPermissionsTestBase):
    """Covers what the redesigned SPL Approvals page actually renders for a
    pending vs. already-decided plan - action buttons only show for a
    pending decision, and a decided plan shows who/when/why instead."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # See the identical note in SPLPricingPlanDecisionTests.setUpTestData -
        # this page only ever shows Roshan League matches.
        from operations.views.helpers import get_roshan_league_competition
        roshan = get_roshan_league_competition()
        cls.match.competition = roshan
        cls.match.save(update_fields=["competition"])

        cls.plan = ClubPricingPlan.objects.create(
            match=cls.match, club=cls.club_a, version=1,
            status=ClubPricingPlan.Status.SUBMITTED_TO_SPL,
        )

    def _get_page(self, username="_test_ops_manager"):
        client = Client()
        client.login(username=username, password="pw")
        return client.get("/operations/reports/spl/approvals/")

    def test_pending_plan_shows_decision_buttons(self):
        response = self._get_page()
        self.assertContains(response, "Approve Pricing Plan")
        self.assertContains(response, "Reject Pricing Plan")

    def test_approved_plan_hides_decision_buttons_and_shows_who_and_when(self):
        self.plan.spl_decision = ClubPricingPlan.SPLDecision.APPROVED
        self.plan.spl_decision_at = timezone.now()
        self.plan.spl_decision_by = self.manager_user
        self.plan.save()
        response = self._get_page()
        self.assertNotContains(response, "Approve Pricing Plan")
        self.assertNotContains(response, "Reject Pricing Plan")
        self.assertContains(response, "Approved by")

    def test_rejected_plan_shows_reason_and_hides_buttons(self):
        self.plan.spl_decision = ClubPricingPlan.SPLDecision.REJECTED
        self.plan.spl_decision_at = timezone.now()
        self.plan.spl_decision_by = self.manager_user
        self.plan.spl_decision_note = "Fix the VIP pricing."
        self.plan.save()
        response = self._get_page()
        self.assertNotContains(response, "Approve Pricing Plan")
        self.assertNotContains(response, "Reject Pricing Plan")
        self.assertContains(response, "Fix the VIP pricing.")

    def test_club_user_cannot_load_the_page(self):
        response = self._get_page(username="_test_club_a")
        self.assertEqual(response.status_code, 302)

    def test_home_away_split_shown_next_to_the_seat_map(self):
        self.plan.home_percentage = 70
        self.plan.save(update_fields=["home_percentage"])
        response = self._get_page()
        self.assertContains(response, "70% Home / 30% Away")

    def test_missing_split_shows_a_placeholder_not_a_blank(self):
        response = self._get_page()
        self.assertContains(response, "Home/Away split not set")


def _tiny_png():
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (200, 200), color=(0, 128, 0)).save(buffer, format="PNG")
    return SimpleUploadedFile("venue.png", buffer.getvalue(), content_type="image/png")


class SPLPricingPlanSnapshotTests(IsolatedMediaMixin, ClubDashboardPermissionsTestBase):
    """Covers generate_seat_map_snapshot(): approving/rejecting a plan with
    at least one positioned category bakes a real PNG (base image + price
    badges) and saves it as a permanent reference, independent of any later
    edit to the live block positions."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from operations.views.helpers import get_roshan_league_competition
        from matches.models import MapPlacement, Venue, VenueImage

        roshan = get_roshan_league_competition()
        cls.venue = Venue.objects.create(name_ar="ملعب تجريبي", name_en="_Test Venue")
        cls.match.competition = roshan
        cls.match.venue = cls.venue
        cls.match.save(update_fields=["competition", "venue"])

        cls.venue_image = VenueImage.objects.create(venue=cls.venue, image=_tiny_png())
        cls.category = VenueSeatingCategory.objects.create(
            venue=cls.venue, club=cls.club_a, code="_TEST CAT",
        )
        cls.placement = MapPlacement.objects.create(
            venue=cls.venue, club=cls.club_a, position_image=cls.venue_image,
            category=cls.category, position_x=40.0, position_y=60.0,
        )
        cls.plan = ClubPricingPlan.objects.create(
            match=cls.match, club=cls.club_a, version=1,
            status=ClubPricingPlan.Status.SUBMITTED_TO_SPL,
        )
        ClubPricingPlanCategoryPrice.objects.create(plan=cls.plan, category=cls.category, price=250)

    def _approve(self):
        client = Client()
        client.login(username="_test_ops_manager", password="pw")
        return client.post(f"/operations/pricing-plan/{self.plan.pk}/spl-approve/")

    def _reject(self, note="Needs corrected pricing."):
        client = Client()
        client.login(username="_test_ops_manager", password="pw")
        return client.post(f"/operations/pricing-plan/{self.plan.pk}/spl-reject/", {"note": note})

    def test_approve_generates_a_snapshot_file(self):
        self._approve()
        self.plan.refresh_from_db()
        self.assertTrue(bool(self.plan.seat_map_snapshot))
        self.assertTrue(self.plan.seat_map_snapshot.name.endswith(".png"))

    def test_reject_generates_a_snapshot_file(self):
        self._reject()
        self.plan.refresh_from_db()
        self.assertTrue(bool(self.plan.seat_map_snapshot))

    def test_snapshot_survives_a_later_position_edit(self):
        """The whole point of the snapshot - it must not change even after
        the live block position it was rendered from is edited or cleared."""
        self._approve()
        self.plan.refresh_from_db()
        snapshot_name_before = self.plan.seat_map_snapshot.name
        self.placement.position_x = 5.0
        self.placement.position_y = 5.0
        self.placement.save()
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.seat_map_snapshot.name, snapshot_name_before)

    def test_generate_seat_map_snapshot_is_a_noop_without_any_position(self):
        self.placement.delete()
        self._approve()
        self.plan.refresh_from_db()
        self.assertFalse(bool(self.plan.seat_map_snapshot))


class ScopedControlPanelAccessTests(IsolatedMediaMixin, ClubDashboardPermissionsTestBase):
    """A Club Manager coordinator (Club.owner) now gets scoped Control
    Panel access to exactly three sections - Matches, Venue Images, Venue
    Categories - see operations.permissions.can_access_limited_control_panel
    and the test_func/get_queryset overrides in control_panel/views/
    matches.py and venue_details.py. Every full-admin path here must stay
    exactly as it was (NoRegressionTests-style coverage for this phase)."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from matches.models import Venue

        cls.venue = Venue.objects.create(name_ar="ملعب أ", name_en="_Test Venue A")
        cls.match.venue = cls.venue
        cls.match.save(update_fields=["venue"])

        cls.venue_image = VenueImage.objects.create(venue=cls.venue, image=_tiny_png())
        cls.category = VenueSeatingCategory.objects.create(
            venue=cls.venue, club=cls.club_a, code="_TEST CAT",
        )

        # A pure Club Viewer (club_account, no owned club) - must NOT get
        # this access, per explicit product decision (they keep using the
        # separate Club Dashboard instead).
        club_viewer_group, _ = Group.objects.get_or_create(name="Club Viewer")
        cls.club_viewer_user = User.objects.create_user(username="_test_club_viewer_only", password="pw")
        cls.club_viewer_user.groups.add(club_viewer_group)
        cls.club_d.club_account = cls.club_viewer_user
        cls.club_d.save(update_fields=["club_account"])

    # --- Matches ---

    def test_coordinator_sees_only_their_own_matches(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get("/control-panel/matches/")
        self.assertEqual(response.status_code, 200)
        matches = list(response.context["matches"])
        self.assertIn(self.match, matches)
        self.assertNotIn(self.unrelated_match, matches)

    def test_coordinator_does_not_see_add_match_button(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get("/control-panel/matches/")
        self.assertNotContains(response, "Add Match")

    def test_coordinator_cannot_open_unrelated_match_for_edit(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get(f"/control-panel/matches/{self.unrelated_match.pk}/edit/")
        self.assertEqual(response.status_code, 404)

    def test_coordinator_can_edit_all_fields_of_their_own_match(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.post(f"/control-panel/matches/{self.match.pk}/edit/", {
            "competition": self.competition.pk,
            "home_club": self.club_a.pk,
            "away_club": self.club_b.pk,
            "slug": self.match.slug,
            "title_ar": "تعديل",
            "title_en": "Edited",
            "ticketing_plan_approved": "on",
        })
        self.assertEqual(response.status_code, 302)
        self.match.refresh_from_db()
        self.assertTrue(self.match.ticketing_plan_approved)
        self.assertEqual(self.match.title_en, "Edited")

    def test_club_viewer_only_cannot_reach_matches_control_panel(self):
        client = Client()
        client.login(username="_test_club_viewer_only", password="pw")
        response = client.get("/control-panel/matches/")
        self.assertEqual(response.status_code, 302)

    def test_full_admin_still_sees_every_match_and_add_button(self):
        client = Client()
        client.login(username="_test_ops_manager", password="pw")
        response = client.get("/control-panel/matches/")
        self.assertEqual(response.status_code, 200)
        matches = list(response.context["matches"])
        self.assertIn(self.match, matches)
        self.assertIn(self.unrelated_match, matches)
        self.assertContains(response, "Add Match")

    # --- Venue Images ---

    def test_coordinator_sees_their_own_venue_image(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get("/control-panel/venue-images/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "_Test Venue A")

    def test_unrelated_coordinator_gets_404_on_this_venue_image_edit(self):
        client = Client()
        client.login(username="_test_club_c", password="pw")
        response = client.get(f"/control-panel/venue-images/{self.venue_image.pk}/edit/")
        self.assertEqual(response.status_code, 404)

    def test_unrelated_coordinator_gets_404_on_position_editor(self):
        client = Client()
        client.login(username="_test_club_c", password="pw")
        response = client.get(f"/control-panel/venue-images/{self.venue_image.pk}/positions/")
        self.assertEqual(response.status_code, 404)

    def test_coordinator_position_editor_auto_selects_the_only_club(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get(f"/control-panel/venue-images/{self.venue_image.pk}/positions/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "_TEST CAT")

    def test_coordinator_can_save_a_position_for_their_own_category(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.post(
            f"/control-panel/venue-images/{self.venue_image.pk}/positions/{self.category.pk}/save/",
            {"x": "33.0", "y": "44.0"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.category.primary_placement.position_x, 33.0)

    def test_unrelated_coordinator_cannot_save_a_position_for_this_category(self):
        client = Client()
        client.login(username="_test_club_c", password="pw")
        response = client.post(
            f"/control-panel/venue-images/{self.venue_image.pk}/positions/{self.category.pk}/save/",
            {"x": "33.0", "y": "44.0"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertIsNone(self.category.primary_placement)

    def test_coordinator_can_upload_a_new_venue_image_for_their_own_venue(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.post("/control-panel/venue-images/new/", {
            "venue": self.venue.pk,
            "image": _tiny_png(),
            "caption": "New seating map",
            "sort_order": 0,
            "is_active": True,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(VenueImage.objects.filter(venue=self.venue, caption="New seating map").exists())

    def test_coordinator_cannot_upload_an_image_for_an_unrelated_venue(self):
        from matches.models import Venue

        other_venue = Venue.objects.create(name_ar="ملعب ب", name_en="_Test Venue B")
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.post("/control-panel/venue-images/new/", {
            "venue": other_venue.pk,
            "image": _tiny_png(),
            "caption": "Should not be allowed",
            "sort_order": 0,
            "is_active": True,
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(VenueImage.objects.filter(caption="Should not be allowed").exists())

    def test_full_admin_still_sees_every_venue_image(self):
        other_venue_for_admin_check = VenueImage.objects.create(venue=self.venue, image=_tiny_png())
        client = Client()
        client.login(username="_test_ops_manager", password="pw")
        response = client.get("/control-panel/venue-images/")
        self.assertEqual(response.status_code, 200)
        images = list(response.context["venue_images"])
        self.assertIn(self.venue_image, images)
        self.assertIn(other_venue_for_admin_check, images)

    # --- Venue Categories ---

    def test_coordinator_sees_only_their_own_categories(self):
        other_club_category = VenueSeatingCategory.objects.create(
            venue=self.venue, club=self.club_c, code="_OTHER CAT",
        )
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get("/control-panel/venue-categories/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "_TEST CAT")
        self.assertNotContains(response, "_OTHER CAT")

    def test_coordinator_cannot_edit_an_unrelated_clubs_category(self):
        other_club_category = VenueSeatingCategory.objects.create(
            venue=self.venue, club=self.club_c, code="_OTHER CAT",
        )
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get(f"/control-panel/venue-categories/{other_club_category.pk}/edit/")
        self.assertEqual(response.status_code, 404)

    def test_coordinator_cannot_toggle_an_unrelated_clubs_category(self):
        other_club_category = VenueSeatingCategory.objects.create(
            venue=self.venue, club=self.club_c, code="_OTHER CAT",
        )
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.post(f"/control-panel/venue-categories/{other_club_category.pk}/toggle-active/")
        self.assertEqual(response.status_code, 404)
        other_club_category.refresh_from_db()
        self.assertTrue(other_club_category.is_active)

    def test_coordinator_can_create_a_category_for_their_own_club_and_venue(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.post("/control-panel/venue-categories/new/", {
            "venue": self.venue.pk,
            "club": self.club_a.pk,
            "code": "_NEW CAT",
            "sort_order": 0,
            "is_active": True,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(VenueSeatingCategory.objects.filter(club=self.club_a, code="_NEW CAT").exists())

    def test_coordinator_cannot_create_a_category_for_an_unrelated_club(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.post("/control-panel/venue-categories/new/", {
            "venue": self.venue.pk,
            "club": self.club_c.pk,
            "code": "_SHOULD NOT EXIST",
            "sort_order": 0,
            "is_active": True,
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(VenueSeatingCategory.objects.filter(code="_SHOULD NOT EXIST").exists())

    def test_full_admin_still_sees_every_category_and_import_export_button(self):
        VenueSeatingCategory.objects.create(venue=self.venue, club=self.club_c, code="_OTHER CAT 2")
        client = Client()
        client.login(username="_test_ops_manager", password="pw")
        response = client.get("/control-panel/venue-categories/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "_TEST CAT")
        self.assertContains(response, "_OTHER CAT 2")
        self.assertContains(response, "Import / Export")

    # --- Control Venue hub (tabbed, coordinator-only) ---

    def test_coordinator_can_open_the_hub(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get("/control-panel/venue-control/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "_TEST CAT")
        self.assertContains(response, "_Test Venue A")
        self.assertContains(response, 'data-tab-button="matches"')
        self.assertContains(response, 'data-tab-panel="images"')
        self.assertContains(response, 'data-tab-panel="categories"')

    def test_hub_shows_only_the_coordinators_own_data(self):
        other_category = VenueSeatingCategory.objects.create(
            venue=self.venue, club=self.club_c, code="_HUB OTHER CAT",
        )
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get("/control-panel/venue-control/")
        self.assertContains(response, "_TEST CAT")
        self.assertNotContains(response, "_HUB OTHER CAT")

    def test_full_admin_cannot_open_the_hub(self):
        """Full admins keep using the existing separate pages/subnav - the
        hub is a narrower, coordinator-only view."""
        client = Client()
        client.login(username="_test_ops_manager", password="pw")
        response = client.get("/control-panel/venue-control/")
        self.assertEqual(response.status_code, 302)

    def test_club_viewer_only_cannot_open_the_hub(self):
        client = Client()
        client.login(username="_test_club_viewer_only", password="pw")
        response = client.get("/control-panel/venue-control/")
        self.assertEqual(response.status_code, 302)

    def test_venue_image_toggle_redirects_back_to_the_images_tab(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.post(f"/control-panel/venue-images/{self.venue_image.pk}/toggle-active/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/control-panel/venue-control/?tab=images")

    def test_category_toggle_redirects_back_to_the_categories_tab(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.post(f"/control-panel/venue-categories/{self.category.pk}/toggle-active/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/control-panel/venue-control/?tab=categories")

    def test_match_update_redirects_back_to_the_matches_tab(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.post(f"/control-panel/matches/{self.match.pk}/edit/", {
            "competition": self.competition.pk,
            "home_club": self.club_a.pk,
            "away_club": self.club_b.pk,
            "slug": self.match.slug,
            "title_ar": "تعديل",
            "title_en": "Edited",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/control-panel/venue-control/?tab=matches")

    def test_full_admin_toggle_still_redirects_to_the_standalone_list(self):
        client = Client()
        client.login(username="_test_ops_manager", password="pw")
        response = client.post(f"/control-panel/venue-images/{self.venue_image.pk}/toggle-active/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/control-panel/venue-images/")

    def test_position_editor_back_link_points_to_the_hub_for_a_coordinator(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get(f"/control-panel/venue-images/{self.venue_image.pk}/positions/")
        self.assertContains(response, "/control-panel/venue-control/?tab=images")

    def test_position_editor_back_link_points_to_the_list_for_an_admin(self):
        client = Client()
        client.login(username="_test_ops_manager", password="pw")
        response = client.get(f"/control-panel/venue-images/{self.venue_image.pk}/positions/", {"club": self.club_a.pk})
        self.assertContains(response, "/control-panel/venue-images/")
        self.assertNotContains(response, "/control-panel/venue-control/")

    # --- Category Import/Export/Template (scoped) ---

    def test_coordinator_can_download_template_for_their_own_venue_and_club(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get("/control-panel/venue-categories/template/", {"venue": self.venue.pk, "club": self.club_a.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def test_coordinator_cannot_download_template_for_an_unrelated_club(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get("/control-panel/venue-categories/template/", {"venue": self.venue.pk, "club": self.club_c.pk})
        self.assertEqual(response.status_code, 400)

    def test_coordinator_can_export_their_own_categories(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get("/control-panel/venue-categories/export/", {"venue": self.venue.pk, "club": self.club_a.pk})
        self.assertEqual(response.status_code, 200)

    def test_coordinator_cannot_export_an_unrelated_clubs_categories(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get("/control-panel/venue-categories/export/", {"venue": self.venue.pk, "club": self.club_c.pk})
        self.assertEqual(response.status_code, 400)

    def test_club_viewer_only_cannot_reach_category_import_export(self):
        client = Client()
        client.login(username="_test_club_viewer_only", password="pw")
        response = client.get("/control-panel/venue-categories/import/")
        self.assertEqual(response.status_code, 302)

    def test_full_admin_still_downloads_template_for_any_club(self):
        client = Client()
        client.login(username="_test_ops_manager", password="pw")
        response = client.get("/control-panel/venue-categories/template/", {"venue": self.venue.pk, "club": self.club_c.pk})
        self.assertEqual(response.status_code, 200)

    # --- Calendar sync (unscoped by explicit product decision) ---

    def test_coordinator_can_reach_the_sync_calendar_confirm_page(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get("/control-panel/matches/sync-calendar/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/control-panel/venue-control/?tab=matches")

    def test_club_viewer_only_cannot_reach_sync_calendar(self):
        client = Client()
        client.login(username="_test_club_viewer_only", password="pw")
        response = client.get("/control-panel/matches/sync-calendar/")
        self.assertEqual(response.status_code, 302)

    def test_full_admin_sync_calendar_back_link_points_to_match_list(self):
        client = Client()
        client.login(username="_test_ops_manager", password="pw")
        response = client.get("/control-panel/matches/sync-calendar/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/control-panel/matches/"')

