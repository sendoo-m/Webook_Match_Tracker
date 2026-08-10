from django.urls import path

from . import views

app_name = "operations"

urlpatterns = [
    path("", views.OperationsDashboardView.as_view(), name="dashboard"),
    path("matches/", views.MatchListView.as_view(), name="match-list"),
    path("calendar/", views.MatchCalendarView.as_view(), name="calendar"),
    path("matches/<int:pk>/", views.MatchDetailView.as_view(), name="match-detail"),
    path("matches/<int:pk>/live/", views.MatchLiveView.as_view(), name="match-live"),
    path("matches/<int:pk>/outstanding/", views.MatchOutstandingItemsView.as_view(), name="match-outstanding"),
    path("matches/<int:pk>/slug/edit/", views.MatchSlugEditView.as_view(), name="match-slug-edit"),
    path("matches/<int:pk>/slug/", views.MatchSlugUpdateView.as_view(), name="match-slug-update"),
    path("matches/<int:pk>/discount/edit/", views.MatchDiscountEditView.as_view(), name="match-discount-edit"),
    path("matches/<int:pk>/discount/", views.MatchDiscountUpdateView.as_view(), name="match-discount-update"),
    path("matches/<int:pk>/spl-info/edit/", views.MatchSPLInfoEditView.as_view(), name="match-spl-info-edit"),
    path("matches/<int:pk>/spl-info/", views.MatchSPLInfoUpdateView.as_view(), name="match-spl-info-update"),
    path("matches/<int:pk>/delayed-details/", views.MatchDelayedDetailsView.as_view(), name="match-delayed-details"),
    path("checklist-items/<int:pk>/update/", views.ChecklistItemUpdateView.as_view(), name="checklist-item-update"),
    path("matches/<int:pk>/send-to-cms/", views.SendToCMSView.as_view(), name="send-to-cms"),
    path("matches/<int:pk>/activity-log/", views.MatchActivityLogListView.as_view(), name="match-activity-log"),
    path("matches/<int:pk>/cms-status/", views.MatchCMSStatusUpdateView.as_view(), name="match-cms-status-update",),
    path("reports/missing-requirements/", views.MissingRequirementsReportView.as_view(),name="missing-requirements-report",),
    path("reports/workload/", views.CoordinatorWorkloadReportView.as_view(), name="workload-report"),
    path("reports/spl/", views.SPLReportView.as_view(), name="spl-report"),
    path("reports/spl/export/", views.SPLReportExportView.as_view(), name="spl-report-export"),
    path("feedback/", views.FeedbackPageView.as_view(), name="feedback"),
    path("feedback/submit/", views.FeedbackSubmitView.as_view(), name="feedback-submit"),
    path("whats-new/", views.ChangelogView.as_view(), name="changelog"),

]