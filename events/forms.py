from zoneinfo import ZoneInfo

from django import forms
from django.contrib.auth import get_user_model

from .models import Category, Event, EventCategoryAccess, EventChecklistCategory, EventChecklistTemplateItem

User = get_user_model()
RIYADH_TZ = ZoneInfo("Asia/Riyadh")


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["group", "name_ar", "name_en", "sort_order", "is_active"]


class EventCategoryAccessForm(forms.ModelForm):
    class Meta:
        model = EventCategoryAccess
        fields = ["user", "category", "role"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["user"].queryset = User.objects.filter(is_active=True).order_by("username")
        self.fields["category"].queryset = Category.objects.filter(is_active=True).order_by(
            "group__sort_order", "sort_order"
        )


class EventChecklistCategoryForm(forms.ModelForm):
    class Meta:
        model = EventChecklistCategory
        fields = ["name", "sort_order"]


class EventChecklistTemplateItemForm(forms.ModelForm):
    class Meta:
        model = EventChecklistTemplateItem
        fields = ["category", "title", "description", "sort_order", "is_required", "is_active"]


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            "category",
            "venue",
            "slug",
            "title_ar",
            "title_en",
            "description_ar",
            "description_en",
            "event_date",
            "start_time",
            "end_time",
            "gates_open_time",
            "sale_starts_at",
            "actual_release_at",
        ]
        widgets = {
            "event_date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
            "gates_open_time": forms.TimeInput(attrs={"type": "time"}),
            "sale_starts_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "actual_release_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "description_ar": forms.Textarea(attrs={"rows": 3}),
            "description_en": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_sale_starts_at(self):
        value = self.cleaned_data.get("sale_starts_at")
        if value:
            return value.replace(tzinfo=RIYADH_TZ)
        return value

    def clean_actual_release_at(self):
        value = self.cleaned_data.get("actual_release_at")
        if value:
            return value.replace(tzinfo=RIYADH_TZ)
        return value


class EventImportForm(forms.Form):
    import_file = forms.FileField(
        label="CSV or Excel file",
        help_text="Columns: slug, category, venue, title_ar, title_en, description_ar, "
        "description_en, event_date, start_time, end_time, gates_open_time, sale_starts_at. "
        "Events are matched/updated by slug.",
    )
    category = forms.ModelChoiceField(
        label="Only import this category",
        queryset=Category.objects.filter(is_active=True).order_by("group__sort_order", "sort_order"),
        required=False,
        help_text="Leave blank to import every row in the file. If set, rows for any other "
        "category are skipped rather than imported.",
    )

    def clean_import_file(self):
        import_file = self.cleaned_data["import_file"]
        if not import_file.name.lower().endswith((".csv", ".xlsx")):
            raise forms.ValidationError("Please upload a .csv or .xlsx file.")
        return import_file


class EventExportFilterForm(forms.Form):
    FORMAT_CHOICES = (
        ("xlsx", "Excel (.xlsx)"),
        ("csv", "CSV"),
    )
    category = forms.ModelChoiceField(
        label="Category",
        queryset=Category.objects.filter(is_active=True).order_by("group__sort_order", "sort_order"),
        required=False,
        empty_label="All categories",
    )
    format = forms.ChoiceField(label="Format", choices=FORMAT_CHOICES, initial="xlsx")
