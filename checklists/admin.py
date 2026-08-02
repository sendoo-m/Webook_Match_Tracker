from django.contrib import admin, messages
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

from .models import ChecklistCategory, ChecklistTemplateItem, MatchChecklistItem
from matches.models import Match


@admin.register(ChecklistCategory)
class ChecklistCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "sort_order")
    ordering = ("sort_order", "id")
    search_fields = ("name",)


@admin.register(ChecklistTemplateItem)
class ChecklistTemplateItemAdmin(admin.ModelAdmin):
    change_list_template = "admin/checklists/checklisttemplateitem/change_list.html"

    list_display = ("title", "category", "sort_order", "is_required", "is_active")
    list_filter = ("category", "is_required", "is_active")
    search_fields = ("title", "description")
    ordering = ("category__sort_order", "sort_order", "id")

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "sync-templates/",
                self.admin_site.admin_view(self.sync_templates_view),
                name="checklists_checklisttemplateitem_sync",
            ),
        ]
        return custom_urls + urls

    def sync_templates_view(self, request):
        if request.method != "POST":
            context = {
                **self.admin_site.each_context(request),
                "opts": self.model._meta,
                "title": "Sync checklist templates",
            }
            return TemplateResponse(
                request,
                "admin/checklists/checklisttemplateitem/sync_confirm.html",
                context,
            )

        templates = list(
            ChecklistTemplateItem.objects.select_related("category").order_by(
                "category__sort_order", "sort_order", "id"
            )
        )
        matches = Match.objects.all()

        created_count = 0
        reactivated_count = 0
        deactivated_count = 0

        template_map = {t.id: t for t in templates}
        active_templates = [t for t in templates if t.is_active]

        for match in matches:
            existing_items = {
                item.template_item_id: item
                for item in MatchChecklistItem.objects.filter(match=match).select_related("template_item")
            }

            for template in active_templates:
                if template.id not in existing_items:
                    MatchChecklistItem.objects.create(
                        match=match,
                        template_item=template,
                        status=MatchChecklistItem.Status.NOT_STARTED,
                        is_active=True,
                    )
                    created_count += 1
                else:
                    item = existing_items[template.id]
                    if not item.is_active:
                        item.is_active = True
                        item.save(update_fields=["is_active"])
                        reactivated_count += 1

            for template_id, item in existing_items.items():
                template = template_map.get(template_id)
                if template and not template.is_active and item.is_active:
                    item.is_active = False
                    item.save(update_fields=["is_active"])
                    deactivated_count += 1

        self.message_user(
            request,
            f"Sync completed successfully. Created: {created_count}, "
            f"reactivated: {reactivated_count}, deactivated: {deactivated_count}.",
            level=messages.SUCCESS,
        )
        return redirect(reverse("admin:checklists_checklisttemplateitem_changelist"))


@admin.register(MatchChecklistItem)
class MatchChecklistItemAdmin(admin.ModelAdmin):
    list_display = (
        "match",
        "template_item",
        "status",
        "is_active",
        "completed_by",
        "completed_at",
    )
    list_filter = (
        "status",
        "is_active",
        "template_item__category",
    )
    search_fields = (
        "match__title_en",
        "match__title_ar",
        "template_item__title",
        "note",
        "delay_reason",
    )
    ordering = (
        "match__event_date",
        "match_id",
        "template_item__category__sort_order",
        "template_item__sort_order",
        "id",
    )