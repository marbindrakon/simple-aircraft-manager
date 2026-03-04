from core import views

ROUTER_REGISTRATIONS = [
    ('aircraft', views.AircraftViewSet),
    ('aircraft-notes', views.AircraftNoteViewSet),
    ('aircraft-events', views.AircraftEventViewSet),
    ('invitation-codes', views.InvitationCodeViewSet, {'basename': 'invitation-code'}),
    ('invitation-code-roles', views.InvitationCodeAircraftRoleViewSet, {'basename': 'invitation-code-role'}),
]
