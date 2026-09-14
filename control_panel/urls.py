from django.urls import path

from . import views

app_name = "control_panel"

urlpatterns = [
    path("", views.PanelHomeView.as_view(), name="home"),

    path("matches/", views.MatchAdminListView.as_view(), name="match-list"),
    path("matches/new/", views.MatchAdminCreateView.as_view(), name="match-create"),
    path("matches/<int:pk>/edit/", views.MatchAdminUpdateView.as_view(), name="match-update"),
    path("matches/export/", views.MatchExportView.as_view(), name="match-export"),
    path("matches/import/", views.MatchImportView.as_view(), name="match-import"),
    path("matches/template/", views.MatchTemplateView.as_view(), name="match-template"),
    path("matches/sync-calendar/", views.MatchSyncCalendarView.as_view(), name="match-sync-calendar"),

    path("teams/", views.TeamListView.as_view(), name="team-list"),
    path("teams/new/", views.TeamCreateView.as_view(), name="team-create"),
    path("teams/<int:pk>/edit/", views.TeamUpdateView.as_view(), name="team-update"),
    path("teams/<int:pk>/toggle-active/", views.TeamToggleActiveView.as_view(), name="team-toggle-active"),

    path("stadiums/", views.StadiumListView.as_view(), name="stadium-list"),
    path("stadiums/new/", views.StadiumCreateView.as_view(), name="stadium-create"),
    path("stadiums/<int:pk>/edit/", views.StadiumUpdateView.as_view(), name="stadium-update"),
    path("stadiums/<int:pk>/toggle-active/", views.StadiumToggleActiveView.as_view(), name="stadium-toggle-active"),

    path("venue-images/", views.VenueImageListView.as_view(), name="venue-image-list"),
    path("venue-images/new/", views.VenueImageCreateView.as_view(), name="venue-image-create"),
    path("venue-images/<int:pk>/edit/", views.VenueImageUpdateView.as_view(), name="venue-image-update"),
    path("venue-images/<int:pk>/toggle-active/", views.VenueImageToggleActiveView.as_view(), name="venue-image-toggle-active"),

    path("venue-categories/", views.VenueSeatingCategoryListView.as_view(), name="venue-category-list"),
    path("venue-categories/new/", views.VenueSeatingCategoryCreateView.as_view(), name="venue-category-create"),
    path("venue-categories/<int:pk>/edit/", views.VenueSeatingCategoryUpdateView.as_view(), name="venue-category-update"),
    path("venue-categories/<int:pk>/toggle-active/", views.VenueSeatingCategoryToggleActiveView.as_view(), name="venue-category-toggle-active"),
    path("venue-categories/import/", views.VenueCategoryImportView.as_view(), name="venue-category-import"),
    path("venue-categories/template/", views.VenueCategoryTemplateView.as_view(), name="venue-category-template"),
    path("venue-categories/export/", views.VenueCategoryExportView.as_view(), name="venue-category-export"),

    path("users/", views.UserListView.as_view(), name="user-list"),
    path("users/new/", views.UserCreateView.as_view(), name="user-create"),
    path("users/<int:pk>/edit/", views.UserUpdateView.as_view(), name="user-update"),
    path("users/<int:pk>/toggle-active/", views.UserToggleActiveView.as_view(), name="user-toggle-active"),
    path("users/<int:pk>/login-as/", views.ImpersonateUserView.as_view(), name="user-login-as"),
    path("stop-impersonating/", views.StopImpersonatingView.as_view(), name="stop-impersonating"),

    path("sections/", views.SectionListView.as_view(), name="section-list"),
    path("sections/new/", views.SectionCreateView.as_view(), name="section-create"),
    path("sections/<int:pk>/edit/", views.SectionUpdateView.as_view(), name="section-update"),
    path("sections/<int:pk>/toggle-active/", views.SectionToggleActiveView.as_view(), name="section-toggle-active"),

    path("checklist-categories/", views.ChecklistCategoryListView.as_view(), name="checklist-category-list"),
    path("checklist-categories/new/", views.ChecklistCategoryCreateView.as_view(), name="checklist-category-create"),
    path("checklist-categories/<int:pk>/edit/", views.ChecklistCategoryUpdateView.as_view(), name="checklist-category-update"),

    path("checklist-items/", views.ChecklistItemListView.as_view(), name="checklist-item-list"),
    path("checklist-items/new/", views.ChecklistItemCreateView.as_view(), name="checklist-item-create"),
    path("checklist-items/<int:pk>/edit/", views.ChecklistItemUpdateView.as_view(), name="checklist-item-update"),
    path("checklist-items/<int:pk>/toggle-active/", views.ChecklistItemToggleActiveView.as_view(), name="checklist-item-toggle-active"),

    path("feedback/", views.FeedbackEntryListView.as_view(), name="feedback-list"),
    path("feedback/new/", views.FeedbackEntryCreateView.as_view(), name="feedback-create"),
    path("feedback/<int:pk>/edit/", views.FeedbackEntryUpdateView.as_view(), name="feedback-update"),

    path("release-notes/", views.ReleaseNoteListView.as_view(), name="release-note-list"),
    path("release-notes/new/", views.ReleaseNoteCreateView.as_view(), name="release-note-create"),
    path("release-notes/<int:pk>/edit/", views.ReleaseNoteUpdateView.as_view(), name="release-note-update"),
]
