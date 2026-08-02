from django.urls import path

from . import views

app_name = "operations"

urlpatterns = [
    path("", views.OperationsDashboardView.as_view(), name="dashboard"),
    path("matches/", views.MatchListView.as_view(), name="match-list"),
    path("matches/<int:pk>/", views.MatchDetailView.as_view(), name="match-detail"),
    path("checklist-items/<int:pk>/update/", views.ChecklistItemUpdateView.as_view(), name="checklist-item-update"),
    path("matches/<int:pk>/send-to-cms/", views.SendToCMSView.as_view(), name="send-to-cms"),
    path("matches/<int:pk>/activity-log/", views.MatchActivityLogListView.as_view(), name="match-activity-log"),
    path("matches/<int:pk>/cms-status/", views.MatchCMSStatusUpdateView.as_view(), name="match-cms-status-update",),
    path("reports/missing-requirements/", views.MissingRequirementsReportView.as_view(),name="missing-requirements-report",),

]