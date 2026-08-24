
from .activity_log import MatchActivityLogListView
from .calendar import CalendarDayMatchesView, MatchCalendarView
from .changelog import ChangelogView
from .checklist import ChecklistItemNoteEditView, ChecklistItemUpdateView
from .cms import MatchCMSStatusUpdateView, SendToCMSView
from .dashboard import OperationsDashboardView
from .delayed_details import MatchDelayedDetailsView
from .discount import MatchDiscountEditView, MatchDiscountUpdateView
from .feedback import FeedbackPageView, FeedbackSubmitView
from .match_detail import MatchDetailView
from .match_list import MatchListView
from .match_live import MatchLiveView
from .match_quick_view import MatchQuickViewView
from .missing_requirements import MissingRequirementsReportView
from .missing_requirements_popup import MissingRequirementsPopupView
from .outstanding import MatchOutstandingItemsView
from .slug import MatchSlugEditView, MatchSlugUpdateView
from .spl_confirm import SPLPlanConfirmView, SPLTicketsConfirmView
from .spl_info import MatchSPLInfoEditView, MatchSPLInfoUpdateView
from .spl_report import SPLReportExportView, SPLReportView
from .team_quick_view import TeamQuickViewView
from .workload import CoordinatorWorkloadReportView
from .auth_views import HtmxLoginView  # <- new import

__all__ = [
    "CalendarDayMatchesView",
    "ChangelogView",
    "MatchCalendarView",
    "ChecklistItemNoteEditView",
    "ChecklistItemUpdateView",
    "CoordinatorWorkloadReportView",
    "MatchActivityLogListView",
    "MatchCMSStatusUpdateView",
    "MatchDelayedDetailsView",
    "MatchDetailView",
    "MatchDiscountEditView",
    "MatchDiscountUpdateView",
    "FeedbackPageView",
    "FeedbackSubmitView",
    "MatchListView",
    "MatchLiveView",
    "MatchOutstandingItemsView",
    "MatchQuickViewView",
    "MatchSPLInfoEditView",
    "MatchSPLInfoUpdateView",
    "MatchSlugEditView",
    "MatchSlugUpdateView",
    "MissingRequirementsPopupView",
    "MissingRequirementsReportView",
    "OperationsDashboardView",
    "SPLPlanConfirmView",
    "SPLTicketsConfirmView",
    "SPLReportExportView",
    "SPLReportView",
    "SendToCMSView",
    "TeamQuickViewView",
    "HtmxLoginView",  # <- new addition
]
