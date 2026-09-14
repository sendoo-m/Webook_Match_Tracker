# accounts/tests.py
#
# Users/permissions list+form page: covers the UX redesign (search,
# filters, sectioned form) without touching any permission logic - every
# test here asserts the underlying data/access is exactly what it was
# before the redesign, just presented differently.

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase

from matches.models import Club, Competition

User = get_user_model()


class UserListAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ops_group, _ = Group.objects.get_or_create(name="Operations Manager")
        cls.ops_user = User.objects.create_user(username="_test_ux_ops", password="pw")
        cls.ops_user.groups.add(ops_group)

        cm_group, _ = Group.objects.get_or_create(name="Club Manager")
        cls.club_manager = User.objects.create_user(username="_test_ux_cm", password="pw")
        cls.club_manager.groups.add(cm_group)

    def test_authorized_user_can_open_list(self):
        client = Client()
        client.login(username="_test_ux_ops", password="pw")
        response = client.get("/control-panel/users/")
        self.assertEqual(response.status_code, 200)

    def test_unauthorized_user_is_denied(self):
        client = Client()
        client.login(username="_test_ux_cm", password="pw")
        response = client.get("/control-panel/users/")
        self.assertEqual(response.status_code, 302)

    def test_anonymous_user_is_redirected_to_login(self):
        client = Client()
        response = client.get("/control-panel/users/")
        self.assertEqual(response.status_code, 302)


class UserListFilterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ops_group, _ = Group.objects.get_or_create(name="Operations Manager")
        cls.admin = User.objects.create_user(username="_test_ux_admin", password="pw")
        cls.admin.groups.add(ops_group)

        cm_group, _ = Group.objects.get_or_create(name="Club Manager")
        cv_group, _ = Group.objects.get_or_create(name="Club Viewer")

        cls.club = Club.objects.create(name_ar="نادي فلتر", name_en="Filter Club")
        cls.coordinator = User.objects.create_user(username="_test_ux_coordinator", password="pw")
        cls.coordinator.groups.add(cm_group)
        cls.club.owner = cls.coordinator
        cls.club.save(update_fields=["owner"])

        cls.club_account_user = User.objects.create_user(
            username="_test_ux_clubviewer", password="pw", is_active=False
        )
        cls.club_account_user.groups.add(cv_group)
        cls.club.club_account = cls.club_account_user
        cls.club.save(update_fields=["club_account"])

    def test_search_filters_by_username(self):
        client = Client()
        client.login(username="_test_ux_admin", password="pw")
        response = client.get("/control-panel/users/", {"q": "_test_ux_coordinator"})
        users = list(response.context["users"])
        self.assertIn(self.coordinator, users)
        self.assertNotIn(self.club_account_user, users)

    def test_role_filter_matches_group(self):
        client = Client()
        client.login(username="_test_ux_admin", password="pw")
        cv_group = Group.objects.get(name="Club Viewer")
        response = client.get("/control-panel/users/", {"role": cv_group.pk})
        users = list(response.context["users"])
        self.assertIn(self.club_account_user, users)
        self.assertNotIn(self.coordinator, users)

    def test_club_filter_matches_both_coordinator_and_direct_account(self):
        """The filter must not leak users unrelated to the club, and must
        catch a club's access through EITHER slot (owner or club_account) -
        the same union get_user_club_ids itself already relies on."""
        client = Client()
        client.login(username="_test_ux_admin", password="pw")
        response = client.get("/control-panel/users/", {"club": self.club.pk})
        users = list(response.context["users"])
        self.assertIn(self.coordinator, users)
        self.assertIn(self.club_account_user, users)
        self.assertNotIn(self.admin, users)

    def test_status_filter_active_excludes_inactive(self):
        client = Client()
        client.login(username="_test_ux_admin", password="pw")
        response = client.get("/control-panel/users/", {"status": "active"})
        users = list(response.context["users"])
        self.assertIn(self.coordinator, users)
        self.assertNotIn(self.club_account_user, users)

    def test_no_filters_does_not_leak_unrelated_data(self):
        """Baseline sanity check: filtering is purely a queryset narrowing,
        never a data-access escalation - an unfiltered request still only
        returns real User rows, nothing from another model."""
        client = Client()
        client.login(username="_test_ux_admin", password="pw")
        response = client.get("/control-panel/users/")
        for user in response.context["users"]:
            self.assertIsInstance(user, User)


class UserFormDataIntegrityTests(TestCase):
    """The redesign must not change what gets saved - every field here was
    already saved by the pre-redesign form; these assert the exact same
    data still round-trips through the new sectioned template."""

    @classmethod
    def setUpTestData(cls):
        ops_group, _ = Group.objects.get_or_create(name="Operations Manager")
        cls.admin = User.objects.create_user(username="_test_ux_admin2", password="pw")
        cls.admin.groups.add(ops_group)

        Group.objects.get_or_create(name="Club Manager")
        cls.club = Club.objects.create(name_ar="نادي فورم", name_en="Form Club")
        cls.competition = Competition.objects.create(name_ar="بطولة فورم", name_en="Form Competition")

    def test_create_user_saves_role_club_and_competition(self):
        client = Client()
        client.login(username="_test_ux_admin2", password="pw")
        cm_group = Group.objects.get(name="Club Manager")

        response = client.post("/control-panel/users/new/", {
            "username": "_test_ux_new",
            "first_name": "Test",
            "last_name": "User",
            "is_active": "on",
            "password": "somepassword123",
            "group": cm_group.pk,
            "owned_clubs": [self.club.pk],
            "club_account": "",
            "competitions": [self.competition.pk],
        })
        self.assertEqual(response.status_code, 302)

        created = User.objects.get(username="_test_ux_new")
        self.assertEqual(list(created.groups.values_list("name", flat=True)), ["Club Manager"])
        self.assertEqual(list(created.owned_clubs.values_list("pk", flat=True)), [self.club.pk])
        self.assertEqual(
            list(created.competition_access.values_list("competition_id", flat=True)), [self.competition.pk]
        )
        self.assertTrue(created.is_active)

    def test_editing_unrelated_field_preserves_existing_access(self):
        """Changing just the first name must not disturb group/club/
        competition access already granted - the whole form resubmits every
        field, so this proves the template's checkbox/select initial values
        are wired correctly and nothing silently resets on save."""
        cm_group = Group.objects.get(name="Club Manager")
        user = User.objects.create_user(username="_test_ux_edit", password="pw", first_name="Old")
        user.groups.add(cm_group)
        self.club.owner = user
        self.club.save(update_fields=["owner"])
        from matches.models import UserCompetitionAccess
        UserCompetitionAccess.objects.create(user=user, competition=self.competition)

        client = Client()
        client.login(username="_test_ux_admin2", password="pw")
        response = client.post(f"/control-panel/users/{user.pk}/edit/", {
            "username": "_test_ux_edit",
            "first_name": "New",
            "last_name": "",
            "is_active": "on",
            "password": "",
            "group": cm_group.pk,
            "owned_clubs": [self.club.pk],
            "club_account": "",
            "competitions": [self.competition.pk],
        })
        self.assertEqual(response.status_code, 302)

        user.refresh_from_db()
        self.assertEqual(user.first_name, "New")
        self.assertEqual(list(user.groups.values_list("name", flat=True)), ["Club Manager"])
        self.assertEqual(list(user.owned_clubs.values_list("pk", flat=True)), [self.club.pk])
        self.assertEqual(
            list(user.competition_access.values_list("competition_id", flat=True)), [self.competition.pk]
        )

    def test_sensitive_role_not_granted_by_omission(self):
        """Leaving the role dropdown at a non-sensitive choice must never
        result in Operations Manager/Viewer access - the group is always
        exactly what was submitted, single-valued, never additive."""
        cm_group = Group.objects.get(name="Club Manager")
        client = Client()
        client.login(username="_test_ux_admin2", password="pw")
        client.post("/control-panel/users/new/", {
            "username": "_test_ux_nonsensitive",
            "first_name": "", "last_name": "", "is_active": "on",
            "password": "somepassword123",
            "group": cm_group.pk,
            "owned_clubs": [], "club_account": "", "competitions": [],
        })
        created = User.objects.get(username="_test_ux_nonsensitive")
        from core.permissions import can_manage_control_panel, is_viewer_only
        self.assertFalse(can_manage_control_panel(created))
        self.assertFalse(is_viewer_only(created))

    def test_direct_post_cannot_grant_superuser(self):
        """The form has no is_superuser field at all - posting one must be
        silently ignored, not escalate the account."""
        cm_group = Group.objects.get(name="Club Manager")
        client = Client()
        client.login(username="_test_ux_admin2", password="pw")
        client.post("/control-panel/users/new/", {
            "username": "_test_ux_escalate",
            "first_name": "", "last_name": "", "is_active": "on",
            "password": "somepassword123",
            "group": cm_group.pk,
            "owned_clubs": [], "club_account": "", "competitions": [],
            "is_superuser": "on",
        })
        created = User.objects.get(username="_test_ux_escalate")
        self.assertFalse(created.is_superuser)
