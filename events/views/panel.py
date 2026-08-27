from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from ..forms import CategoryForm, EventCategoryAccessForm, EventChecklistCategoryForm, EventChecklistTemplateItemForm
from ..models import Category, EventCategoryAccess, EventChecklistCategory, EventChecklistTemplateItem
from .base import EventsPanelAccessMixin, EventsPanelCreateView, EventsPanelListView, EventsPanelUpdateView


class EventsPanelHomeView(LoginRequiredMixin, EventsPanelAccessMixin, TemplateView):
    template_name = "events/panel/home.html"


class CategoryListView(EventsPanelListView):
    model = Category
    template_name = "events/panel/category_list.html"
    context_object_name = "categories"
    ordering = ["group__sort_order", "sort_order", "id"]
    page_title = _("Categories")
    create_url_name = "events:category-create"
    create_label = _("Add Category")

    def get_queryset(self):
        return super().get_queryset().select_related("group")


class CategoryCreateView(EventsPanelCreateView):
    model = Category
    form_class = CategoryForm
    template_name = "events/panel/category_form.html"
    success_url = reverse_lazy("events:category-list")
    success_message = _("Category created.")
    page_title = _("Add Category")
    list_url_name = "events:category-list"


class CategoryUpdateView(EventsPanelUpdateView):
    model = Category
    form_class = CategoryForm
    template_name = "events/panel/category_form.html"
    success_url = reverse_lazy("events:category-list")
    success_message = _("Category updated.")
    page_title = _("Edit Category")
    list_url_name = "events:category-list"


class EventCategoryAccessListView(EventsPanelListView):
    model = EventCategoryAccess
    template_name = "events/panel/access_list.html"
    context_object_name = "grants"
    ordering = ["category__group__sort_order", "category__sort_order", "user__username"]
    page_title = _("Category Access")
    create_url_name = "events:access-create"
    create_label = _("Grant Access")

    def get_queryset(self):
        return super().get_queryset().select_related("user", "category", "category__group")


class EventCategoryAccessCreateView(EventsPanelCreateView):
    model = EventCategoryAccess
    form_class = EventCategoryAccessForm
    template_name = "events/panel/access_form.html"
    success_url = reverse_lazy("events:access-list")
    success_message = _("Access granted.")
    page_title = _("Grant Category Access")
    list_url_name = "events:access-list"


class EventCategoryAccessUpdateView(EventsPanelUpdateView):
    model = EventCategoryAccess
    form_class = EventCategoryAccessForm
    template_name = "events/panel/access_form.html"
    success_url = reverse_lazy("events:access-list")
    success_message = _("Access updated.")
    page_title = _("Edit Category Access")
    list_url_name = "events:access-list"


class EventChecklistCategoryListView(EventsPanelListView):
    model = EventChecklistCategory
    template_name = "events/panel/checklistcategory_list.html"
    context_object_name = "categories"
    ordering = ["sort_order", "name"]
    page_title = _("Checklist Categories")
    create_url_name = "events:checklist-category-create"
    create_label = _("Add Category")


class EventChecklistCategoryCreateView(EventsPanelCreateView):
    model = EventChecklistCategory
    form_class = EventChecklistCategoryForm
    template_name = "events/panel/checklistcategory_form.html"
    success_url = reverse_lazy("events:checklist-category-list")
    success_message = _("Checklist category created.")
    page_title = _("Add Checklist Category")
    list_url_name = "events:checklist-category-list"


class EventChecklistCategoryUpdateView(EventsPanelUpdateView):
    model = EventChecklistCategory
    form_class = EventChecklistCategoryForm
    template_name = "events/panel/checklistcategory_form.html"
    success_url = reverse_lazy("events:checklist-category-list")
    success_message = _("Checklist category updated.")
    page_title = _("Edit Checklist Category")
    list_url_name = "events:checklist-category-list"


class EventChecklistItemListView(EventsPanelListView):
    model = EventChecklistTemplateItem
    template_name = "events/panel/checklisttemplateitem_list.html"
    context_object_name = "items"
    ordering = ["category__sort_order", "sort_order", "title"]
    page_title = _("Checklist Items")
    create_url_name = "events:checklist-item-create"
    create_label = _("Add Item")

    def get_queryset(self):
        return super().get_queryset().select_related("category")


class EventChecklistItemCreateView(EventsPanelCreateView):
    model = EventChecklistTemplateItem
    form_class = EventChecklistTemplateItemForm
    template_name = "events/panel/checklisttemplateitem_form.html"
    success_url = reverse_lazy("events:checklist-item-list")
    success_message = _("Checklist item created.")
    page_title = _("Add Checklist Item")
    list_url_name = "events:checklist-item-list"


class EventChecklistTemplateItemUpdateView(EventsPanelUpdateView):
    model = EventChecklistTemplateItem
    form_class = EventChecklistTemplateItemForm
    template_name = "events/panel/checklisttemplateitem_form.html"
    success_url = reverse_lazy("events:checklist-item-list")
    success_message = _("Checklist item updated.")
    page_title = _("Edit Checklist Item")
    list_url_name = "events:checklist-item-list"
