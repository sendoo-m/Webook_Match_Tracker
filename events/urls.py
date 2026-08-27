from django.urls import path

from . import views

app_name = "events"

urlpatterns = [
    path("", views.EventsDashboardView.as_view(), name="dashboard"),

    path("events/<int:pk>/", views.EventDetailView.as_view(), name="event-detail"),
    path("events/<int:pk>/send-to-cms/", views.EventSendToCMSView.as_view(), name="event-send-to-cms"),
    path("events/<int:pk>/cms-status/", views.EventCMSStatusUpdateView.as_view(), name="event-cms-status-update"),
    path("checklist-items/<int:pk>/update/", views.EventChecklistItemUpdateView.as_view(), name="event-checklist-item-update"),

    path("panel/", views.EventsPanelHomeView.as_view(), name="panel-home"),

    path("panel/events/", views.EventAdminListView.as_view(), name="event-list"),
    path("panel/events/new/", views.EventAdminCreateView.as_view(), name="event-create"),
    path("panel/events/<int:pk>/edit/", views.EventAdminUpdateView.as_view(), name="event-update"),
    path("panel/events/export/", views.EventExportView.as_view(), name="event-export"),
    path("panel/events/import/", views.EventImportView.as_view(), name="event-import"),
    path("panel/events/template/", views.EventTemplateView.as_view(), name="event-template"),

    path("panel/categories/", views.CategoryListView.as_view(), name="category-list"),
    path("panel/categories/new/", views.CategoryCreateView.as_view(), name="category-create"),
    path("panel/categories/<int:pk>/edit/", views.CategoryUpdateView.as_view(), name="category-update"),

    path("panel/access/", views.EventCategoryAccessListView.as_view(), name="access-list"),
    path("panel/access/new/", views.EventCategoryAccessCreateView.as_view(), name="access-create"),
    path("panel/access/<int:pk>/edit/", views.EventCategoryAccessUpdateView.as_view(), name="access-update"),

    path("panel/checklist-categories/", views.EventChecklistCategoryListView.as_view(), name="checklist-category-list"),
    path("panel/checklist-categories/new/", views.EventChecklistCategoryCreateView.as_view(), name="checklist-category-create"),
    path("panel/checklist-categories/<int:pk>/edit/", views.EventChecklistCategoryUpdateView.as_view(), name="checklist-category-update"),

    path("panel/checklist-items/", views.EventChecklistItemListView.as_view(), name="checklist-item-list"),
    path("panel/checklist-items/new/", views.EventChecklistItemCreateView.as_view(), name="checklist-item-create"),
    path("panel/checklist-items/<int:pk>/edit/", views.EventChecklistTemplateItemUpdateView.as_view(), name="checklist-item-update"),
]
