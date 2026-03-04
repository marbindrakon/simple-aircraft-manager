"""
core.views package.

All names are re-exported here so that existing imports of the form
    from core.views import SomeView
continue to work without modification.

urls.py and any other callers do NOT need to be updated.
"""

# Aircraft API viewset
from core.views.aircraft import AircraftViewSet

# Note / event viewsets + healthz
from core.views.notes_events import (
    AircraftNoteViewSet,
    AircraftEventViewSet,
    healthz,
)

# Template views (HTML pages)
from core.views.template_views import (
    DashboardView,
    AircraftDetailView,
    SquawkHistoryView,
)

# Logbook import UI
from core.views.logbook_import_view import LogbookImportView

# Public / share-link views
from core.views.public_views import PublicAircraftView

# Auth: logout, register, profile
from core.views.auth_views import (
    custom_logout,
    RegisterView,
    ProfileView,
)

# Import/export
from core.views.import_export_views import (
    ExportView,
    ImportView,
    ImportJobStatusView,
)

# User search
from core.views.user_views import UserSearchView

# Invitation / admin viewsets + manage views
from core.views.invitations import (
    InvitationCodeViewSet,
    InvitationCodeAircraftRoleViewSet,
    ManageInvitationsView,
    ManageInvitationDetailView,
    ManageUsersView,
)

__all__ = [
    "AircraftViewSet",
    "AircraftNoteViewSet",
    "AircraftEventViewSet",
    "healthz",
    "DashboardView",
    "AircraftDetailView",
    "SquawkHistoryView",
    "LogbookImportView",
    "PublicAircraftView",
    "custom_logout",
    "RegisterView",
    "ProfileView",
    "ExportView",
    "ImportView",
    "ImportJobStatusView",
    "UserSearchView",
    "InvitationCodeViewSet",
    "InvitationCodeAircraftRoleViewSet",
    "ManageInvitationsView",
    "ManageInvitationDetailView",
    "ManageUsersView",
]
