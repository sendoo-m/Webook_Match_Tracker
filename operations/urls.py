from django.urls import path

from . import views

app_name = "operations"

urlpatterns = [
    path("", views.OperationsDashboardView.as_view(), name="dashboard"),
    path("matches/", views.MatchListView.as_view(), name="match-list"),
    path("calendar/", views.MatchCalendarView.as_view(), name="calendar"),
    path(
        "calendar/<int:year>/<int:month>/<int:day>/matches/",
        views.CalendarDayMatchesView.as_view(),
        name="calendar-day-matches",
    ),
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
    path("matches/<int:pk>/quick-view/", views.MatchQuickViewView.as_view(), name="match-quick-view"),
    path(
        "matches/<int:pk>/missing-requirements-popup/",
        views.MissingRequirementsPopupView.as_view(),
        name="missing-requirements-popup",
    ),
    path("teams/<int:club_id>/quick-view/", views.TeamQuickViewView.as_view(), name="team-quick-view"),
    path("checklist-items/<int:pk>/update/", views.ChecklistItemUpdateView.as_view(), name="checklist-item-update"),
    path("checklist-items/<int:pk>/note-edit/", views.ChecklistItemNoteEditView.as_view(), name="checklist-item-note-edit"),
    path("matches/<int:pk>/send-to-cms/", views.SendToCMSView.as_view(), name="send-to-cms"),
    path("matches/<int:pk>/activity-log/", views.MatchActivityLogListView.as_view(), name="match-activity-log"),
    path("matches/<int:pk>/activity/", views.MatchActivityView.as_view(), name="match-activity"),
    path("matches/<int:pk>/cms-status/", views.MatchCMSStatusUpdateView.as_view(), name="match-cms-status-update",),
    path("matches/<int:pk>/webook-link/", views.MatchWebookLinkUpdateView.as_view(), name="match-webook-link-update"),
    path("reports/missing-requirements/", views.MissingRequirementsReportView.as_view(),name="missing-requirements-report",),
    path("reports/workload/", views.CoordinatorWorkloadReportView.as_view(), name="workload-report"),
    path("release-schedule/", views.MatchReleaseScheduleView.as_view(), name="release-schedule"),
    path("matches/<int:pk>/release-delay/", views.MatchReleaseDelayUpdateView.as_view(), name="release-delay-update"),
    path("reports/spl/", views.SPLReportView.as_view(), name="spl-report"),
    path("reports/spl/export/", views.SPLReportExportView.as_view(), name="spl-report-export"),
    path("reports/spl/approvals/", views.SPLApprovalsView.as_view(), name="spl-approvals"),
    path("reports/spl/finished/", views.SPLFinishedMatchesView.as_view(), name="spl-finished-matches"),
    path("matches/<int:pk>/spl-plan-confirm/", views.SPLPlanConfirmView.as_view(), name="spl-plan-confirm"),
    path("matches/<int:pk>/spl-tickets-confirm/", views.SPLTicketsConfirmView.as_view(), name="spl-tickets-confirm"),
    path(
        "matches/<int:pk>/spl-plan-approval-upload/",
        views.SPLPlanApprovalUploadView.as_view(),
        name="spl-plan-approval-upload",
    ),
    path(
        "pricing-plan/<int:pk>/spl-approve/",
        views.SPLPricingPlanApproveView.as_view(),
        name="spl-pricing-plan-approve",
    ),
    path(
        "pricing-plan/<int:pk>/spl-reject/",
        views.SPLPricingPlanRejectView.as_view(),
        name="spl-pricing-plan-reject",
    ),
    path("club-dashboard/", views.ClubDashboardView.as_view(), name="club-dashboard"),
    path("club-dashboard/schedule/", views.ClubDashboardScheduleView.as_view(), name="club-dashboard-schedule"),
    path(
        "club-dashboard/matches/<int:pk>/",
        views.ClubDashboardMatchDetailView.as_view(),
        name="club-dashboard-match-detail",
    ),
    path(
        "club-dashboard/matches/<int:pk>/pricing-plan/upload/",
        views.ClubPricingPlanUploadView.as_view(),
        name="club-pricing-plan-upload",
    ),
    path(
        "club-dashboard/matches/<int:pk>/pricing-plan/import/",
        views.ClubPricingPlanCategoryImportView.as_view(),
        name="club-pricing-plan-category-import",
    ),
    path(
        "club-dashboard/pricing-plan/<int:pk>/download/",
        views.ClubPricingPlanDownloadView.as_view(),
        name="club-pricing-plan-download",
    ),
    path(
        "club-dashboard/pricing-plan/<int:pk>/submit/",
        views.ClubPricingPlanSubmitView.as_view(),
        name="club-pricing-plan-submit",
    ),
    path(
        "club-dashboard/pricing-plan/<int:pk>/confirm-submission/",
        views.ClubPricingPlanConfirmSubmissionView.as_view(),
        name="club-pricing-plan-confirm-submission",
    ),
    path("feedback/", views.FeedbackPageView.as_view(), name="feedback"),
    path("feedback/submit/", views.FeedbackSubmitView.as_view(), name="feedback-submit"),
    path("whats-new/", views.ChangelogView.as_view(), name="changelog"),

    path("notifications/", views.NotificationListView.as_view(), name="notification-list"),
    path("notifications/badge/", views.NotificationBadgeView.as_view(), name="notification-badge"),
    path("notifications/<int:pk>/read/", views.NotificationMarkReadView.as_view(), name="notification-mark-read"),
    path("notifications/mark-all-read/", views.NotificationMarkAllReadView.as_view(), name="notification-mark-all-read"),

]