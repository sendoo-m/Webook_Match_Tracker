from django.contrib import admin

from .models import MatchActivityLog


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