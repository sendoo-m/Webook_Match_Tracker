from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.utils import timezone

from matches.models import Club, Competition, Match
from notifications.models import Notification
from notifications.services import run_daily_notification_sweep


class DailyNotificationSweepTests(TestCase):
    """Real ORM fixtures (no mocks), covering the day-25/day-20 boundaries,
    match-live firing once, and re-running the sweep never duplicating a
    notification for the same (recipient, type, match) - the guarantees the
    plan called out explicitly for this phase."""

    @classmethod
    def setUpTestData(cls):
        cls.competition = Competition.objects.create(name_ar="دوري تجريبي", name_en="Test League")

        club_manager_group, _ = Group.objects.get_or_create(name="Club Manager")
        club_viewer_group, _ = Group.objects.get_or_create(name="Club Viewer")
        viewer_group, _ = Group.objects.get_or_create(name="Viewer")

        cls.coordinator = User.objects.create_user(username="_test_notif_coordinator", password="pw")
        cls.coordinator.groups.add(club_manager_group)
        cls.club_account_user = User.objects.create_user(username="_test_notif_clubviewer", password="pw")
        cls.club_account_user.groups.add(club_viewer_group)

        cls.away_coordinator = User.objects.create_user(username="_test_notif_away_coordinator", password="pw")
        cls.away_coordinator.groups.add(club_manager_group)

        cls.spl_user = User.objects.create_user(username="_test_notif_spl", password="pw")
        cls.spl_user.groups.add(viewer_group)

        cls.home_club = Club.objects.create(
            name_ar="نادي المضيف", name_en="Home Club",
            owner=cls.coordinator, club_account=cls.club_account_user,
        )
        cls.away_club = Club.objects.create(
            name_ar="نادي الضيف", name_en="Away Club", owner=cls.away_coordinator,
        )

    def _make_match(self, *, days_from_now, published=False, slug):
        return Match.objects.create(
            competition=self.competition,
            home_club=self.home_club,
            away_club=self.away_club,
            slug=slug,
            title_ar="مباراة تجريبية",
            title_en="Test Match",
            event_date=(timezone.localdate() + timedelta(days=days_from_now)),
            cms_status=Match.Status.PUBLISHED if published else Match.Status.DRAFT,
        )

    def test_fires_25_day_club_notice_to_owner_and_club_account(self):
        match = self._make_match(days_from_now=25, slug="_test-25-day")
        run_daily_notification_sweep()
        recipients = set(
            Notification.objects.filter(
                match=match, notification_type=Notification.NotificationType.MATCH_25_DAYS
            ).values_list("recipient_id", flat=True)
        )
        self.assertEqual(recipients, {self.coordinator.id, self.club_account_user.id})

    def test_no_25_day_notice_at_24_or_26_days(self):
        match_24 = self._make_match(days_from_now=24, slug="_test-24-day")
        match_26 = self._make_match(days_from_now=26, slug="_test-26-day")
        run_daily_notification_sweep()
        self.assertFalse(
            Notification.objects.filter(
                match__in=[match_24, match_26], notification_type=Notification.NotificationType.MATCH_25_DAYS
            ).exists()
        )

    def test_fires_20_day_coordinator_notice_only_when_not_live(self):
        not_live = self._make_match(days_from_now=20, slug="_test-20-day-not-live")
        live = self._make_match(days_from_now=20, published=True, slug="_test-20-day-live")
        run_daily_notification_sweep()

        not_live_recipients = set(
            Notification.objects.filter(
                match=not_live, notification_type=Notification.NotificationType.MATCH_20_DAYS_NOT_LIVE
            ).values_list("recipient_id", flat=True)
        )
        self.assertEqual(not_live_recipients, {self.coordinator.id})
        # Club Viewer account is not the coordinator - excluded from this notice.
        self.assertNotIn(self.club_account_user.id, not_live_recipients)

        self.assertFalse(
            Notification.objects.filter(
                match=live, notification_type=Notification.NotificationType.MATCH_20_DAYS_NOT_LIVE
            ).exists()
        )

    def test_match_live_notifies_spl_and_both_clubs_once(self):
        match = self._make_match(days_from_now=10, published=True, slug="_test-live")
        run_daily_notification_sweep()
        recipients = set(
            Notification.objects.filter(
                match=match, notification_type=Notification.NotificationType.MATCH_LIVE
            ).values_list("recipient_id", flat=True)
        )
        self.assertEqual(
            recipients,
            {self.spl_user.id, self.coordinator.id, self.club_account_user.id, self.away_coordinator.id},
        )

        # Running the sweep again the same day (or any day after) must not
        # create duplicates for a match that stays live.
        run_daily_notification_sweep()
        self.assertEqual(
            Notification.objects.filter(
                match=match, notification_type=Notification.NotificationType.MATCH_LIVE
            ).count(),
            len(recipients),
        )

    def test_rerunning_sweep_does_not_duplicate_25_day_notice(self):
        match = self._make_match(days_from_now=25, slug="_test-25-day-rerun")
        run_daily_notification_sweep()
        first_count = Notification.objects.filter(
            match=match, notification_type=Notification.NotificationType.MATCH_25_DAYS
        ).count()
        run_daily_notification_sweep()
        second_count = Notification.objects.filter(
            match=match, notification_type=Notification.NotificationType.MATCH_25_DAYS
        ).count()
        self.assertEqual(first_count, second_count)
