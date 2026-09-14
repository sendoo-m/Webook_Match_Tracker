# core/permissions.py
#
# Domain-agnostic role checks shared across every app (operations, events,
# control_panel). Nothing here knows about Match, Event, Club, or Category -
# it only ever asks "is this user a manager / super admin / viewer", based
# on Django Groups. Anything that answers "can this user act on THIS
# specific match/event/club" belongs in that domain's own permissions.py
# (see operations/permissions.py, events/permissions.py), not here.
#
# Moved out of operations/permissions.py during the modular-monolith
# restructuring: events/permissions.py and several control_panel files used
# to import these straight from operations, which meant two otherwise
# independent apps (events, control_panel) both depended on the football-
# specific operations app just to check "is this a manager". They now
# import from here instead. operations/permissions.py still re-exports the
# same names for backward compatibility, so no other file's imports needed
# to change.

MANAGER_GROUPS = {"Operations Manager", "Super Admin"}
VIEWER_GROUPS = {"Viewer"}


def can_manage_control_panel(user):
    """
    True for users allowed into the Control Panel (Operations Manager /
    Super Admin): full back-office CRUD over clubs, venues, competitions,
    users, and checklist templates — everything except Django's own /admin/.

    This is ONLY about Control Panel access. It does NOT mean the user can
    edit a match's checklist/CMS status in the operations app — see
    operations.permissions.user_can_manage_match for that.
    """
    if not getattr(user, "is_authenticated", False):
        return False

    return user.is_superuser or user.groups.filter(
        name__in=MANAGER_GROUPS
    ).exists()


def is_super_admin(user):
    """
    True only for the top-tier accounts: Django superuser or in the
    "Super Admin" group. Stricter than can_manage_control_panel (which also
    lets Operations Manager in) - this gates user impersonation ("login
    as"), where only the most trusted accounts should be allowed, and no
    account at this level can be impersonated by another.
    """
    if not getattr(user, "is_authenticated", False):
        return False

    return user.is_superuser or user.groups.filter(name="Super Admin").exists()


def is_club_viewer(user):
    """
    True for any account in the "Club Viewer" group specifically, checked
    on group membership alone - regardless of is_superuser or any other
    group the account might also carry. This is the real football-club
    audience's own account type: it gets exactly the Club Dashboard,
    Calendar, and Release Schedule pages, never the internal Operations
    Dashboard/Events/Missing Requirements pages (see
    operations.permissions.ExcludeClubViewerAccessMixin).

    Deliberately separate from "Club Manager", which is used by internal
    coordinators who need full operations access AND happen to also own
    a club's data - conflating the two groups previously caused a real
    incident where a restriction meant for real club accounts also
    locked out coordinators (see the revert of commit c1bdee6). Do not
    reuse this function's group check for anything coordinator-facing.
    """
    if not getattr(user, "is_authenticated", False):
        return False

    return user.groups.filter(name="Club Viewer").exists()


def is_viewer_only(user):
    """
    True for accounts whose ENTIRE access is the read-only Viewer role (the
    external SPL monitoring team) - never true for anyone who is also a
    manager/admin, even if they happen to also sit in the "Viewer" group.
    Gates the simplified Viewer dashboard/sidebar and the narrow SPL-plan
    confirmation action.
    """
    if not getattr(user, "is_authenticated", False):
        return False

    if can_manage_control_panel(user):
        return False

    return user.groups.filter(name__in=VIEWER_GROUPS).exists()
