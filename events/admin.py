from django.contrib import admin, messages
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

from .models import (
    Category,
    CategoryGroup,
    Event,
    EventActivityLog,
    EventCategoryAccess,
    EventChecklistCategory,
    EventChecklistItem,
    EventChecklistTemplateItem,
)


@admin.register(CategoryGroup)
class CategoryGroupAdmin(admin.ModelAdmin):
    list_display = ("name_en", "code", "sort_order")
    ordering = ("sort_order", "id")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name_en", "group", "sort_order", "is_active")
    list_filter = ("group", "is_active")
    search_fields = ("name_en", "name_ar")
    ordering = ("group__sort_order", "sort_order", "id")


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title_en", "category", "event_date", "cms_status")
    list_filter = ("category__group", "category", "cms_status")
    search_fields = ("title_en", "title_ar", "slug")
    ordering = ("-event_date", "-id")


@admin.register(EventChecklistCategory)
class EventChecklistCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "sort_order")
    ordering = ("sort_order", "id")
    search_fields = ("name",)


@admin.register(EventChecklistTemplateItem)
class EventChecklistTemplateItemAdmin(admin.ModelAdmin):
    change_list_template = "admin/events/eventchecklisttemplateitem/change_list.html"

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
                name="events_eventchecklisttemplateitem_sync",
            ),
        ]
        return custom_urls + urls

    def sync_templates_view(self, request):
        if request.method != "POST":
            context = {
                **self.admin_site.each_context(request),
                "opts": self.model._meta,
                "title": "Sync event checklist templates",
            }
            return TemplateResponse(
                request,
                "admin/events/eventchecklisttemplateitem/sync_confirm.html",
                context,
            )

        templates = list(
            EventChecklistTemplateItem.objects.select_related("category").order_by(
                "category__sort_order", "sort_order", "id"
            )
        )
        events = Event.objects.all()

        created_count = 0
        reactivated_count = 0
        deactivated_count = 0

        template_map = {t.id: t for t in templates}
        active_templates = [t for t in templates if t.is_active]

        for event in events:
            existing_items = {
                item.template_item_id: item
                for item in EventChecklistItem.objects.filter(event=event).select_related("template_item")
            }

            for template in active_templates:
                if template.id not in existing_items:
                    EventChecklistItem.objects.create(
                        event=event,
                        template_item=template,
                        status=EventChecklistItem.Status.NOT_STARTED,
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
        return redirect(reverse("admin:events_eventchecklisttemplateitem_changelist"))


@admin.register(EventChecklistItem)
class EventChecklistItemAdmin(admin.ModelAdmin):
    list_display = ("event", "template_item", "status", "is_active", "completed_by", "completed_at")
    list_filter = ("status", "is_active", "template_item__category")
    search_fields = ("event__title_en", "event__title_ar", "template_item__title", "note", "delay_reason")
    ordering = ("event__event_date", "event_id", "template_item__category__sort_order", "template_item__sort_order", "id")


@admin.register(EventActivityLog)
class EventActivityLogAdmin(admin.ModelAdmin):
    list_display = ("event", "action", "user", "created_at")
    list_filter = ("action",)
    ordering = ("-created_at",)


@admin.register(EventCategoryAccess)
class EventCategoryAccessAdmin(admin.ModelAdmin):
    list_display = ("user", "category", "role", "granted_at")
    list_filter = ("role", "category__group")
    search_fields = ("user__username", "category__name_en")
