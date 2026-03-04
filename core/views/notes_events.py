import logging

from django.utils import timezone
from rest_framework import viewsets
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from core.events import log_event
from core.mixins import AircraftScopedMixin, EventLoggingMixin
from core.models import AircraftNote, AircraftEvent
from core.serializers import (
    AircraftNoteSerializer, AircraftNoteNestedSerializer,
    AircraftNoteCreateUpdateSerializer, AircraftEventSerializer,
)

logger = logging.getLogger(__name__)

class AircraftNoteViewSet(AircraftScopedMixin, EventLoggingMixin, viewsets.ModelViewSet):
    queryset = AircraftNote.objects.all().order_by('-added_timestamp')
    serializer_class = AircraftNoteSerializer
    aircraft_fk_path = 'aircraft'
    event_category = 'note'
    event_name_created = 'Note added'
    event_name_deleted = 'Note deleted'

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return AircraftNoteCreateUpdateSerializer
        return AircraftNoteNestedSerializer

    def perform_update(self, serializer):
        """Set edited_timestamp when note is updated"""
        instance = serializer.save(edited_timestamp=timezone.now())
        aircraft = instance.aircraft
        user = self.request.user if hasattr(self, 'request') else None
        log_event(aircraft, 'note', "Note updated", user=user)


class AircraftEventViewSet(viewsets.ReadOnlyModelViewSet):
    from rest_framework.pagination import PageNumberPagination

    class _Pagination(PageNumberPagination):
        page_size = 100
        max_page_size = 200

    queryset = AircraftEvent.objects.all()
    serializer_class = AircraftEventSerializer
    pagination_class = _Pagination

@require_GET
def healthz(request):
    return JsonResponse({"status": "ok"})

