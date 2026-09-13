from django.contrib import admin

from .models import ClubPricingPlan, MatchActivityLog


@admin.register(MatchActivityLog)
class MatchActivityLogAdmin(admin.ModelAdmin):
    list_display = ("match", "action", "user", "created_at")
    list_filter = ("action", "created_at")
    search_fields = (
        "match__title_en",
        "match__title_ar",
        "user__username",
        "user__email",
        "description",
    )
    autocomplete_fields = ("match", "user")
    ordering = ("-created_at", "-id")


@admin.register(ClubPricingPlan)
class ClubPricingPlanAdmin(admin.ModelAdmin):
    list_display = ("match", "club", "version", "status", "uploaded_by", "uploaded_at")
    list_filter = ("status", "uploaded_at")
    search_fields = ("match__title_en", "match__title_ar", "club__name_en", "club__name_ar")
    autocomplete_fields = ("match", "club", "uploaded_by")
    ordering = ("-uploaded_at",)