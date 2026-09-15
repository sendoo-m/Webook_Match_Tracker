
from .calendar import CalendarDayMatchesView, MatchCalendarView
from .changelog import ChangelogView
from .cms import MatchCMSStatusUpdateView, MatchWebookLinkUpdateView, SendToCMSView
from .dashboard import OperationsDashboardView
from .delayed_details import MatchDelayedDetailsView
from .discount import MatchDiscountEditView, MatchDiscountUpdateView
from .feedback import FeedbackPageView, FeedbackSubmitView
from .match_detail import MatchDetailView
from .match_list import MatchListView
from .match_live import MatchLiveView
from .match_quick_view import MatchQuickViewView
from .outstanding import MatchOutstandingItemsView
from .release_schedule import MatchReleaseDelayUpdateView, MatchReleaseScheduleView
from .slug import MatchSlugEditView, MatchSlugUpdateView
from .team_quick_view import TeamQuickViewView

# SPL and Club Dashboard views/forms now live in their own apps
# (modular-monolith restructuring). Re-exported here unchanged so
# operations/urls.py's `views.SPLReportView`/`views.ClubDashboardView`
# (etc.) and any other existing `from operations.views import X` keep
# working without changes.
from spl.views import (  # noqa: F401 - re-exported for backward compatibility
    MatchSPLInfoEditView,
    MatchSPLInfoUpdateView,
    SPLApprovalsView,
    SPLFinishedMatchesView,
    SPLPlanApprovalUploadView,
    SPLPlanConfirmView,
    SPLPricingPlanApproveView,
    SPLPricingPlanRejectView,
    SPLReportExportView,
    SPLReportView,
    SPLTicketsConfirmView,
)
from clubs.views import (  # noqa: F401 - re-exported for backward compatibility
    ClubDashboardMatchActivityView,
    ClubDashboardMatchDetailView,
    ClubDashboardScheduleView,
    ClubDashboardView,
    ClubPricingPlanCategoryImportView,
    ClubPricingPlanCategoryTemplateView,
    ClubPricingPlanConfirmSubmissionView,
    ClubPricingPlanDownloadView,
    ClubPricingPlanSubmitView,
    ClubPricingPlanUploadView,
)
from reports.views import (  # noqa: F401 - re-exported for backward compatibility
    CoordinatorWorkloadReportView,
    MissingRequirementsPopupView,
    MissingRequirementsReportView,
)
from audit.views import (  # noqa: F401 - re-exported for backward compatibility
    MatchActivityLogListView,
    MatchActivityView,
)
from checklists.views import (  # noqa: F401 - re-exported for backward compatibility
    ChecklistItemNoteEditView,
    ChecklistItemUpdateView,
)
from notifications.views import (  # noqa: F401 - re-exported for backward compatibility
    NotificationBadgeView,
    NotificationListView,
    NotificationMarkAllReadView,
    NotificationMarkReadView,
)
from .auth_views import HtmxLoginView  # <- new import

__all__ = [
    "CalendarDayMatchesView",
    "ChangelogView",
    "MatchCalendarView",
    "ChecklistItemNoteEditView",
    "ChecklistItemUpdateView",
    "ClubDashboardMatchActivityView",
    "ClubDashboardMatchDetailView",
    "ClubDashboardScheduleView",
    "ClubDashboardView",
    "ClubPricingPlanCategoryImportView",
    "ClubPricingPlanCategoryTemplateView",
    "ClubPricingPlanConfirmSubmissionView",
    "ClubPricingPlanDownloadView",
    "ClubPricingPlanSubmitView",
    "ClubPricingPlanUploadView",
    "CoordinatorWorkloadReportView",
    "MatchActivityLogListView",
    "MatchActivityView",
    "MatchCMSStatusUpdateView",
    "MatchWebookLinkUpdateView",
    "MatchDelayedDetailsView",
    "MatchDetailView",
    "MatchDiscountEditView",
    "MatchDiscountUpdateView",
    "FeedbackPageView",
    "FeedbackSubmitView",
    "MatchListView",
    "MatchLiveView",
    "MatchOutstandingItemsView",
    "MatchReleaseDelayUpdateView",
    "MatchReleaseScheduleView",
    "MatchQuickViewView",
    "MatchSPLInfoEditView",
    "MatchSPLInfoUpdateView",
    "MatchSlugEditView",
    "MatchSlugUpdateView",
    "MissingRequirementsPopupView",
    "MissingRequirementsReportView",
    "NotificationBadgeView",
    "NotificationListView",
    "NotificationMarkAllReadView",
    "NotificationMarkReadView",
    "OperationsDashboardView",
    "SPLApprovalsView",
    "SPLFinishedMatchesView",
    "SPLPlanApprovalUploadView",
    "SPLPlanConfirmView",
    "SPLPricingPlanApproveView",
    "SPLPricingPlanRejectView",
    "SPLTicketsConfirmView",
    "SPLReportExportView",
    "SPLReportView",
    "SendToCMSView",
    "TeamQuickViewView",
    "HtmxLoginView",  # <- new addition
]
