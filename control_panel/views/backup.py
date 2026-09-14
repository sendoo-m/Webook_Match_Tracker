# control_panel/views/backup.py
#
# The single most destructive page in this codebase - gated by
# BackupAccessMixin (Super Admin only, stricter than the rest of the
# Control Panel), and every restore action requires typing an exact
# confirmation phrase into a text field before the POST is accepted, on top
# of core.backup.restore_backup's own safety-backup-first/validate-before-
# touching-anything-live procedure.

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views import View

from control_panel.permissions import BackupAccessMixin
from core.backup import BACKUPS_DIR, BackupError, create_backup, list_backups, restore_backup

RESTORE_CONFIRMATION_PHRASE = "RESTORE DATABASE"


def _safe_backup_path(name):
    """Resolves a backup filename to a path strictly inside BACKUPS_DIR -
    never trusts the name outright, since it comes straight from the URL/
    POST data and this page can destroy the live database."""
    candidate = (BACKUPS_DIR / name).resolve()
    if candidate.parent != BACKUPS_DIR.resolve() or not candidate.name.startswith("backup-") or not candidate.name.endswith(".zip"):
        return None
    return candidate


class BackupListView(LoginRequiredMixin, BackupAccessMixin, View):
    template_name = "control_panel/backup_list.html"

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, {
            "backups": list_backups(),
            "confirmation_phrase": RESTORE_CONFIRMATION_PHRASE,
            "page_title": _("Database Backups"),
        })


class BackupCreateView(LoginRequiredMixin, BackupAccessMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            zip_path = create_backup(label="manual")
        except BackupError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, _("Backup created: %(name)s") % {"name": zip_path.name})
        return redirect("control_panel:backup-list")


class BackupDownloadView(LoginRequiredMixin, BackupAccessMixin, View):
    def get(self, request, name, *args, **kwargs):
        path = _safe_backup_path(name)
        if not path or not path.exists():
            raise Http404("Backup not found.")
        return FileResponse(open(path, "rb"), as_attachment=True, filename=path.name)


class BackupRestoreView(LoginRequiredMixin, BackupAccessMixin, View):
    """Restores from an already-existing backup file on disk - requires
    typing the exact confirmation phrase, not just a JS confirm()."""

    def post(self, request, name, *args, **kwargs):
        path = _safe_backup_path(name)
        if not path or not path.exists():
            raise Http404("Backup not found.")

        if request.POST.get("confirmation") != RESTORE_CONFIRMATION_PHRASE:
            messages.error(request, _('Restore cancelled: confirmation phrase did not match "%(phrase)s".') % {"phrase": RESTORE_CONFIRMATION_PHRASE})
            return redirect("control_panel:backup-list")

        try:
            with open(path, "rb") as f:
                safety_backup_path = restore_backup(f)
        except BackupError as exc:
            messages.error(request, str(exc))
            return redirect("control_panel:backup-list")

        messages.success(
            request,
            _("Database restored from %(name)s. The pre-restore state was saved as %(safety)s.")
            % {"name": path.name, "safety": safety_backup_path.name},
        )
        return redirect("control_panel:backup-list")


class BackupUploadRestoreView(LoginRequiredMixin, BackupAccessMixin, View):
    """Restores from an uploaded .zip file (same format create_backup
    produces) - same confirmation-phrase requirement as restoring an
    existing backup."""

    def post(self, request, *args, **kwargs):
        if request.POST.get("confirmation") != RESTORE_CONFIRMATION_PHRASE:
            messages.error(request, _('Restore cancelled: confirmation phrase did not match "%(phrase)s".') % {"phrase": RESTORE_CONFIRMATION_PHRASE})
            return redirect("control_panel:backup-list")

        uploaded_file = request.FILES.get("backup_file")
        if not uploaded_file:
            messages.error(request, _("Please choose a backup .zip file to upload."))
            return redirect("control_panel:backup-list")

        try:
            safety_backup_path = restore_backup(uploaded_file)
        except BackupError as exc:
            messages.error(request, str(exc))
            return redirect("control_panel:backup-list")

        messages.success(
            request,
            _("Database restored from the uploaded file. The pre-restore state was saved as %(safety)s.")
            % {"safety": safety_backup_path.name},
        )
        return redirect("control_panel:backup-list")
