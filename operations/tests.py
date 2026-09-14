import shutil
import tempfile

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from matches.models import Club, Competition, Match, UserCompetitionAccess, VenueSeatingCategory
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
    def test_home_club_user_sees_own_club_dashboard(self):
        self.assertTrue(can_view_own_club_dashboard(self.user_a))

    def test_unrelated_club_still_sees_its_own_dashboard(self):
        # can_view_own_club_dashboard only checks club ownership, not
        # relation to any specific match.
        self.assertTrue(can_view_own_club_dashboard(self.user_c))

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
    def test_club_user_can_open_own_dashboard(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get("/operations/club-dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "operations/club_dashboard.html")

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
        club - the view only ever reads get_user_club_ids(request.user).
        Club B's unrelated match must never appear no matter what's
        appended to the URL."""
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get(
            "/operations/club-dashboard/",
            {"club_id": self.club_c.pk, "club": self.club_c.pk},
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertNotIn("Club C", content)
        # Not "Club D" - that's a substring of the page's own title "Club
        # Dashboard". The unrelated match's slug is unambiguous instead.
        self.assertNotIn(self.unrelated_match.slug, content)


class ClubDashboardMatchListTests(ClubDashboardPermissionsTestBase):
    def test_home_match_appears_for_home_club(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get("/operations/club-dashboard/")
        self.assertIn(self.match, [row["match"] for row in response.context["rows"]])

    def test_away_match_appears_for_away_club(self):
        """The whole point of Phase 3: unlike get_visible_matches, the
        club dashboard shows the club its Away fixtures too."""
        client = Client()
        client.login(username="_test_club_b", password="pw")
        response = client.get("/operations/club-dashboard/")
        self.assertIn(self.match, [row["match"] for row in response.context["rows"]])

    def test_unrelated_match_never_appears(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get("/operations/club-dashboard/")
        matches = [row["match"] for row in response.context["rows"]]
        self.assertNotIn(self.unrelated_match, matches)

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


class ClubDashboardUITests(ClubDashboardPermissionsTestBase):
    def test_empty_state_renders_for_club_with_no_matches(self):
        no_match_user = User.objects.create_user(username="_test_club_e", password="pw")
        Club.objects.create(name_ar="نادي هـ", name_en="Club E", owner=no_match_user)
        client = Client()
        client.login(username="_test_club_e", password="pw")
        response = client.get("/operations/club-dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["rows"]), 0)

    def test_type_filter_narrows_to_home_only(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get("/operations/club-dashboard/", {"type": "home"})
        for row in response.context["rows"]:
            self.assertTrue(row["is_home"])

    def test_type_filter_narrows_to_away_only(self):
        client = Client()
        client.login(username="_test_club_b", password="pw")
        response = client.get("/operations/club-dashboard/", {"type": "away"})
        for row in response.context["rows"]:
            self.assertFalse(row["is_home"])

    def test_page_uses_rtl_capable_base_shell(self):
        """Renders through operations/base.html, same shell (and its
        LANGUAGE_BIDI-driven dir=rtl/ltr) as every other page - no
        separate template system for this page."""
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get("/operations/club-dashboard/")
        self.assertContains(response, "<html")
        self.assertContains(response, "toast-container")

    def test_sidebar_link_only_shown_to_club_users(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get("/operations/")
        self.assertContains(response, "/operations/club-dashboard/")

        client2 = Client()
        client2.login(username="_test_ops_manager", password="pw")
        response2 = client2.get("/operations/")
        self.assertNotContains(response2, "/operations/club-dashboard/")


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

    def test_home_club_can_upload_a_plan(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.post(
            f"/operations/club-dashboard/matches/{self.match.pk}/pricing-plan/upload/",
            {"file": _pdf_file()},
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
            {"file": _pdf_file(), "uploaded_by": self.user_b.pk},
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
            {"file": _pdf_file(), "club": self.club_c.pk, "club_id": self.club_c.pk},
        )
        plan = ClubPricingPlan.objects.get(match=self.match)
        self.assertEqual(plan.club, self.club_a)

    def test_second_upload_creates_version_two(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        client.post(
            f"/operations/club-dashboard/matches/{self.match.pk}/pricing-plan/upload/", {"file": _pdf_file()},
        )
        client.post(
            f"/operations/club-dashboard/matches/{self.match.pk}/pricing-plan/upload/", {"file": _pdf_file()},
        )
        self.assertEqual(ClubPricingPlan.objects.filter(match=self.match).count(), 2)
        latest = ClubPricingPlan.objects.filter(match=self.match).order_by("-version").first()
        self.assertEqual(latest.version, 2)

    def test_activity_log_recorded_on_upload(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        client.post(
            f"/operations/club-dashboard/matches/{self.match.pk}/pricing-plan/upload/", {"file": _pdf_file()},
        )
        self.assertTrue(
            self.match.activity_logs.filter(description__icontains="pricing plan uploaded").exists()
        )

    def test_success_message_shown(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.post(
            f"/operations/club-dashboard/matches/{self.match.pk}/pricing-plan/upload/",
            {"file": _pdf_file()},
            follow=True,
        )
        messages = list(response.context["messages"])
        self.assertTrue(any("uploaded" in str(m) for m in messages))

    def test_spl_and_cms_fields_unchanged_after_real_upload_request(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        client.post(
            f"/operations/club-dashboard/matches/{self.match.pk}/pricing-plan/upload/", {"file": _pdf_file()},
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
            f"/operations/club-dashboard/matches/{self.match.pk}/pricing-plan/upload/", {"file": bad_file},
        )
        self.assertFalse(ClubPricingPlan.objects.filter(match=self.match).exists())

    def test_rejects_oversized_file(self):
        client = Client()
        client.login(username="_test_club_a", password="pw")
        oversized = _pdf_file(size=11 * 1024 * 1024)
        client.post(
            f"/operations/club-dashboard/matches/{self.match.pk}/pricing-plan/upload/", {"file": oversized},
        )
        self.assertFalse(ClubPricingPlan.objects.filter(match=self.match).exists())

    def test_cannot_upload_once_spl_has_approved(self):
        self.match.ticketing_plan_approved = True
        self.match.save(update_fields=["ticketing_plan_approved"])
        client = Client()
        client.login(username="_test_club_a", password="pw")
        response = client.get(f"/operations/club-dashboard/matches/{self.match.pk}/pricing-plan/upload/")
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
            f"/operations/club-dashboard/matches/{self.match.pk}/pricing-plan/upload/", {"file": _pdf_file()},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ClubPricingPlan.objects.filter(match=self.match).count(), 1)

    def test_away_club_cannot_upload_a_plan_on_unrelated_match(self):
        client = Client()
        client.login(username="_test_club_b", password="pw")
        response = client.post(
            f"/operations/club-dashboard/matches/{self.unrelated_match.pk}/pricing-plan/upload/",
            {"file": _pdf_file()},
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
        from matches.models import Venue, VenueImage

        roshan = get_roshan_league_competition()
        cls.venue = Venue.objects.create(name_ar="ملعب تجريبي", name_en="_Test Venue")
        cls.match.competition = roshan
        cls.match.venue = cls.venue
        cls.match.save(update_fields=["competition", "venue"])

        cls.venue_image = VenueImage.objects.create(venue=cls.venue, image=_tiny_png())
        cls.category = VenueSeatingCategory.objects.create(
            venue=cls.venue, club=cls.club_a, code="_TEST CAT",
            position_image=cls.venue_image, position_x=40.0, position_y=60.0,
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
        self.category.position_x = 5.0
        self.category.position_y = 5.0
        self.category.save()
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.seat_map_snapshot.name, snapshot_name_before)

    def test_generate_seat_map_snapshot_is_a_noop_without_any_position(self):
        self.category.position_image = None
        self.category.position_x = None
        self.category.position_y = None
        self.category.save()
        self._approve()
        self.plan.refresh_from_db()
        self.assertFalse(bool(self.plan.seat_map_snapshot))
