
from .activity_log import MatchActivityLogListView
from .calendar import MatchCalendarView
from .changelog import ChangelogView
from .checklist import ChecklistItemUpdateView
from .cms import MatchCMSStatusUpdateView, SendToCMSView
from .dashboard import OperationsDashboardView
from .delayed_details import MatchDelayedDetailsView
from .discount import MatchDiscountEditView, MatchDiscountUpdateView
from .feedback import FeedbackPageView, FeedbackSubmitView
from .match_detail import MatchDetailView
from .match_list import MatchListView
from .match_live import MatchLiveView
from .missing_requirements import MissingRequirementsReportView
from .outstanding import MatchOutstandingItemsView
from .slug import MatchSlugEditView, MatchSlugUpdateView
from .spl_info import MatchSPLInfoEditView, MatchSPLInfoUpdateView
from .spl_report import SPLReportExportView, SPLReportView
from .workload import CoordinatorWorkloadReportView
from .auth_views import HtmxLoginView  # <- new import

__all__ = [
    "ChangelogView",
    "MatchCalendarView",
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
    "MatchSPLInfoEditView",
    "MatchSPLInfoUpdateView",
    "MatchSlugEditView",
    "MatchSlugUpdateView",
    "MissingRequirementsReportView",
    "OperationsDashboardView",
    "SPLReportExportView",
    "SPLReportView",
    "SendToCMSView",
    "HtmxLoginView",  # <- new addition
]
