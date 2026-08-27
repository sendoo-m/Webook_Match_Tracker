# control_panel/views/impersonate.py

import logging

from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext as _
from django.views import View

from control_panel.permissions import SuperAdminAccessMixin
from operations.permissions import is_super_admin

User = get_user_model()
logger = logging.getLogger(__name__)

IMPERSONATOR_SESSION_KEY = "impersonator_id"
AUTH_BACKEND = "django.contrib.auth.backends.ModelBackend"


class ImpersonateUserView(LoginRequiredMixin, SuperAdminAccessMixin, View):
    """Lets a Super Admin log in as any other, non-admin account for
    support/debugging without knowing their password."""

    def post(self, request, pk, *args, **kwargs):
        target = get_object_or_404(User, pk=pk)

        if target.pk == request.user.pk:
            messages.info(request, _("You're already logged in as this account."))
            return redirect("control_panel:user-list")

        if is_super_admin(target):
            messages.error(request, _("You can't log in as another admin account."))
            return redirect("control_panel:user-list")

        if not target.is_active:
            messages.error(request, _("You can't log in as a deactivated account."))
            return redirect("control_panel:user-list")

        original_user_id = request.user.pk
        original_username = request.user.username

        # login() flushes the session whenever the authenticated user
        # actually changes, so the original account's id has to be stashed
        # AFTER this call, not before, or it gets wiped along with it.
        login(request, target, backend=AUTH_BACKEND)
        request.session[IMPERSONATOR_SESSION_KEY] = original_user_id

        logger.info("Super Admin %s started impersonating %s", original_username, target.username)
        messages.success(request, _("You're now logged in as %(name)s.") % {"name": target.get_full_name() or target.username})
        return redirect("operations:dashboard")


class StopImpersonatingView(LoginRequiredMixin, View):
    """Restores the original Super Admin session. Not gated by
    SuperAdminAccessMixin - by the time this runs, request.user IS the
    impersonated (non-admin) account."""

    def post(self, request, *args, **kwargs):
        original_user_id = request.session.get(IMPERSONATOR_SESSION_KEY)
        if not original_user_id:
            return redirect("operations:dashboard")

        impersonated_username = request.user.username

        try:
            original_user = User.objects.get(pk=original_user_id)
        except User.DoesNotExist:
            auth_logout(request)
            messages.error(request, _("Couldn't restore your original session - please log in again."))
            return redirect("login")

        login(request, original_user, backend=AUTH_BACKEND)
        logger.info("%s stopped impersonating %s", original_user.username, impersonated_username)
        messages.success(request, _("You're back in your own account."))
        return redirect("control_panel:user-list")
