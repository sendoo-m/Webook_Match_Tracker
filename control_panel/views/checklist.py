from django.urls import reverse_lazy

from checklists.models import ChecklistCategory, ChecklistTemplateItem
from control_panel.forms import ChecklistCategoryForm, ChecklistTemplateItemForm

from .base import PanelCreateView, PanelListView, PanelToggleActiveView, PanelUpdateView


class ChecklistCategoryListView(PanelListView):
    model = ChecklistCategory
    template_name = "control_panel/checklistcategory_list.html"
    context_object_name = "categories"
    ordering = ["sort_order", "name"]
    page_title = "Checklist Categories"
    create_url_name = "control_panel:checklist-category-create"
    create_label = "Add Category"


class ChecklistCategoryCreateView(PanelCreateView):
    model = ChecklistCategory
    form_class = ChecklistCategoryForm
    template_name = "control_panel/checklistcategory_form.html"
    success_url = reverse_lazy("control_panel:checklist-category-list")
    success_message = "Checklist category created."
    page_title = "Add Checklist Category"
    list_url_name = "control_panel:checklist-category-list"


class ChecklistCategoryUpdateView(PanelUpdateView):
    model = ChecklistCategory
    form_class = ChecklistCategoryForm
    template_name = "control_panel/checklistcategory_form.html"
    success_url = reverse_lazy("control_panel:checklist-category-list")
    success_message = "Checklist category updated."
    page_title = "Edit Checklist Category"
    list_url_name = "control_panel:checklist-category-list"


class ChecklistItemListView(PanelListView):
    model = ChecklistTemplateItem
    template_name = "control_panel/checklisttemplateitem_list.html"
    context_object_name = "items"
    ordering = ["category__sort_order", "sort_order", "title"]
    page_title = "Checklist Items"
    create_url_name = "control_panel:checklist-item-create"
    create_label = "Add Item"

    def get_queryset(self):
        return super().get_queryset().select_related("category")


class ChecklistItemCreateView(PanelCreateView):
    model = ChecklistTemplateItem
    form_class = ChecklistTemplateItemForm
    template_name = "control_panel/checklisttemplateitem_form.html"
    success_url = reverse_lazy("control_panel:checklist-item-list")
    success_message = "Checklist item created."
    page_title = "Add Checklist Item"
    list_url_name = "control_panel:checklist-item-list"


class ChecklistItemUpdateView(PanelUpdateView):
    model = ChecklistTemplateItem
    form_class = ChecklistTemplateItemForm
    template_name = "control_panel/checklisttemplateitem_form.html"
    success_url = reverse_lazy("control_panel:checklist-item-list")
    success_message = "Checklist item updated."
    page_title = "Edit Checklist Item"
    list_url_name = "control_panel:checklist-item-list"


class ChecklistItemToggleActiveView(PanelToggleActiveView):
    model = ChecklistTemplateItem
    success_url_name = "control_panel:checklist-item-list"
