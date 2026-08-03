
from .activity_log import MatchActivityLogListView
from .checklist import ChecklistItemUpdateView
from .cms import MatchCMSStatusUpdateView, SendToCMSView
from .dashboard import OperationsDashboardView
from .match_detail import MatchDetailView
from .match_list import MatchListView
from .match_live import MatchLiveView
from .missing_requirements import MissingRequirementsReportView
from .outstanding import MatchOutstandingItemsView
from .slug import MatchSlugEditView, MatchSlugUpdateView
from .workload import CoordinatorWorkloadReportView
from .auth_views import HtmxLoginView  # <- new import

__all__ = [
    "ChecklistItemUpdateView",
    "CoordinatorWorkloadReportView",
    "MatchActivityLogListView",
    "MatchCMSStatusUpdateView",
    "MatchDetailView",
    "MatchListView",
    "MatchLiveView",
    "MatchOutstandingItemsView",
    "MatchSlugEditView",
    "MatchSlugUpdateView",
    "MissingRequirementsReportView",
    "OperationsDashboardView",
    "SendToCMSView",
    "HtmxLoginView",  # <- new addition
]
