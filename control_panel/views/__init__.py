from .checklist import (
    ChecklistCategoryCreateView,
    ChecklistCategoryListView,
    ChecklistCategoryUpdateView,
    ChecklistItemCreateView,
    ChecklistItemListView,
    ChecklistItemToggleActiveView,
    ChecklistItemUpdateView,
)
from .clubs import TeamCreateView, TeamListView, TeamToggleActiveView, TeamUpdateView
from .competitions import (
    SectionCreateView,
    SectionListView,
    SectionToggleActiveView,
    SectionUpdateView,
)
from .feedback import FeedbackEntryCreateView, FeedbackEntryListView, FeedbackEntryUpdateView
from .home import PanelHomeView
from .matches import (
    MatchAdminCreateView,
    MatchAdminListView,
    MatchAdminUpdateView,
    MatchExportView,
    MatchImportView,
    MatchSyncCalendarView,
    MatchTemplateView,
)
from .release_notes import ReleaseNoteCreateView, ReleaseNoteListView, ReleaseNoteUpdateView
from .site_settings import SiteSettingsUpdateView
from .venue_details import (
    VenueCategoryExportView,
    VenueCategoryImportView,
    VenueCategoryTemplateView,
    VenueImageCreateView,
    VenueImageListView,
    VenueImageToggleActiveView,
    VenueImageUpdateView,
    VenueSeatingCategoryCreateView,
    VenueSeatingCategoryListView,
    VenueSeatingCategoryToggleActiveView,
    VenueSeatingCategoryUpdateView,
)
from .venues import (
    StadiumCreateView,
    StadiumListView,
    StadiumToggleActiveView,
    StadiumUpdateView,
)

# User management and impersonation now live in the accounts app
# (modular-monolith restructuring). Re-exported here unchanged so
# control_panel/urls.py's `views.UserListView`/`views.ImpersonateUserView`
# (etc.) keep working without changes.
from accounts.views import (  # noqa: F401 - re-exported for backward compatibility
    ImpersonateUserView,
    StopImpersonatingView,
    UserCreateView,
    UserListView,
    UserToggleActiveView,
    UserUpdateView,
)

__all__ = [
    "ChecklistCategoryCreateView",
    "ChecklistCategoryListView",
    "ChecklistCategoryUpdateView",
    "ChecklistItemCreateView",
    "ChecklistItemListView",
    "ChecklistItemToggleActiveView",
    "ChecklistItemUpdateView",
    "FeedbackEntryCreateView",
    "FeedbackEntryListView",
    "FeedbackEntryUpdateView",
    "ImpersonateUserView",
    "MatchAdminCreateView",
    "MatchAdminListView",
    "MatchAdminUpdateView",
    "MatchExportView",
    "MatchImportView",
    "MatchSyncCalendarView",
    "MatchTemplateView",
    "PanelHomeView",
    "ReleaseNoteCreateView",
    "ReleaseNoteListView",
    "ReleaseNoteUpdateView",
    "SectionCreateView",
    "SectionListView",
    "SectionToggleActiveView",
    "SectionUpdateView",
    "SiteSettingsUpdateView",
    "StadiumCreateView",
    "StadiumListView",
    "StadiumToggleActiveView",
    "StadiumUpdateView",
    "StopImpersonatingView",
    "TeamCreateView",
    "TeamListView",
    "TeamToggleActiveView",
    "TeamUpdateView",
    "UserCreateView",
    "UserListView",
    "UserToggleActiveView",
    "UserUpdateView",
    "VenueCategoryExportView",
    "VenueCategoryImportView",
    "VenueCategoryTemplateView",
    "VenueImageCreateView",
    "VenueImageListView",
    "VenueImageToggleActiveView",
    "VenueImageUpdateView",
    "VenueSeatingCategoryCreateView",
    "VenueSeatingCategoryListView",
    "VenueSeatingCategoryToggleActiveView",
    "VenueSeatingCategoryUpdateView",
]
