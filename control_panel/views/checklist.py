from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

from checklists.models import ChecklistCategory, ChecklistTemplateItem
from control_panel.forms import ChecklistCategoryForm, ChecklistTemplateItemForm

from .base import PanelCreateView, PanelListView, PanelToggleActiveView, PanelUpdateView


class ChecklistCategoryListView(PanelListView):
    model = ChecklistCategory
    template_name = "control_panel/checklistcategory_list.html"
    context_object_name = "categories"
    ordering = ["sort_order", "name"]
    page_title = _("Checklist Categories")
    create_url_name = "control_panel:checklist-category-create"
    create_label = _("Add Category")


class ChecklistCategoryCreateView(PanelCreateView):
    model = ChecklistCategory
    form_class = ChecklistCategoryForm
    template_name = "control_panel/checklistcategory_form.html"
    success_url = reverse_lazy("control_panel:checklist-category-list")
    success_message = _("Checklist category created.")
    page_title = _("Add Checklist Category")
    list_url_name = "control_panel:checklist-category-list"


class ChecklistCategoryUpdateView(PanelUpdateView):
    model = ChecklistCategory
    form_class = ChecklistCategoryForm
    template_name = "control_panel/checklistcategory_form.html"
    success_url = reverse_lazy("control_panel:checklist-category-list")
    success_message = _("Checklist category updated.")
    page_title = _("Edit Checklist Category")
    list_url_name = "control_panel:checklist-category-list"


class ChecklistItemListView(PanelListView):
    model = ChecklistTemplateItem
    template_name = "control_panel/checklisttemplateitem_list.html"
    context_object_name = "items"
    ordering = ["category__sort_order", "sort_order", "title"]
    page_title = _("Checklist Items")
    create_url_name = "control_panel:checklist-item-create"
    create_label = _("Add Item")

    def get_queryset(self):
        return super().get_queryset().select_related("category")


class ChecklistItemCreateView(PanelCreateView):
    model = ChecklistTemplateItem
    form_class = ChecklistTemplateItemForm
    template_name = "control_panel/checklisttemplateitem_form.html"
    success_url = reverse_lazy("control_panel:checklist-item-list")
    success_message = _("Checklist item created.")
    page_title = _("Add Checklist Item")
    list_url_name = "control_panel:checklist-item-list"


class ChecklistItemUpdateView(PanelUpdateView):
    model = ChecklistTemplateItem
    form_class = ChecklistTemplateItemForm
    template_name = "control_panel/checklisttemplateitem_form.html"
    success_url = reverse_lazy("control_panel:checklist-item-list")
    success_message = _("Checklist item updated.")
    page_title = _("Edit Checklist Item")
    list_url_name = "control_panel:checklist-item-list"


class ChecklistItemToggleActiveView(PanelToggleActiveView):
    model = ChecklistTemplateItem
    success_url_name = "control_panel:checklist-item-list"
