from core.models import Aircraft, AircraftNote, AircraftEvent
from core.serializers import (
    AircraftSerializer, AircraftListSerializer, AircraftNoteSerializer,
    AircraftNoteNestedSerializer, AircraftNoteCreateUpdateSerializer,
    AircraftEventSerializer,
)
from django.utils import timezone
from health.models import Component, LogbookEntry, Squawk, Document, DocumentCollection, OilRecord, FuelRecord
from health.serializers import (
    ComponentSerializer, LogbookEntrySerializer, SquawkSerializer,
    SquawkNestedSerializer, SquawkCreateUpdateSerializer,
    DocumentCollectionNestedSerializer, DocumentNestedSerializer,
    OilRecordNestedSerializer, OilRecordCreateSerializer,
    FuelRecordNestedSerializer, FuelRecordCreateSerializer,
)

from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from decimal import Decimal


class AircraftViewSet(viewsets.ModelViewSet):
    queryset = Aircraft.objects.all()
    serializer_class = AircraftSerializer

    def get_serializer_class(self):
        """Use lightweight serializer for list, full serializer for detail."""
        if self.action == 'list':
            return AircraftListSerializer
        return AircraftSerializer

    @action(detail=True, methods=['post'])
    def update_hours(self, request, pk=None):
        """
        Update aircraft hours and automatically sync to all in-service components
        POST /api/aircraft/{id}/update_hours/

        Body: {
            "new_hours": 1234.5
        }
        """
        aircraft = self.get_object()
        new_hours = request.data.get('new_hours')

        # Validation
        if new_hours is None:
            return Response({'error': 'new_hours required'},
                          status=status.HTTP_400_BAD_REQUEST)

        try:
            new_hours = Decimal(str(new_hours))
        except:
            return Response({'error': 'Invalid hours value'},
                          status=status.HTTP_400_BAD_REQUEST)

        if new_hours < aircraft.flight_time:
            return Response({'error': 'Hours cannot decrease'},
                          status=status.HTTP_400_BAD_REQUEST)

        hours_delta = new_hours - aircraft.flight_time
        old_hours = aircraft.flight_time

        # Update aircraft
        aircraft.flight_time = new_hours
        aircraft.save()

        # ALWAYS update all in-service components (not optional)
        components = aircraft.components.filter(status='IN-USE')
        updated_components = []
        for component in components:
            component.hours_in_service += hours_delta
            component.hours_since_overhaul += hours_delta
            component.save()
            updated_components.append(str(component.id))

        return Response({
            'success': True,
            'aircraft_hours': float(aircraft.flight_time),
            'hours_added': float(hours_delta),
            'components_updated': len(updated_components),
        })

    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        """
        Get aircraft summary with components, recent logs, active squawks, notes
        GET /api/aircraft/{id}/summary/
        """
        aircraft = self.get_object()

        return Response({
            'aircraft': AircraftSerializer(aircraft, context={'request': request}).data,
            'components': ComponentSerializer(
                aircraft.components.all(),
                many=True,
                context={'request': request}
            ).data,
            'recent_logs': LogbookEntrySerializer(
                aircraft.logbook_entries.order_by('-date')[:10],
                many=True,
                context={'request': request}
            ).data,
            'active_squawks': SquawkNestedSerializer(
                aircraft.squawks.filter(resolved=False),
                many=True,
                context={'request': request}
            ).data,
            'notes': AircraftNoteNestedSerializer(
                aircraft.notes.order_by('-added_timestamp'),
                many=True,
                context={'request': request}
            ).data,
        })

    @action(detail=True, methods=['get'])
    def documents(self, request, pk=None):
        """
        Get aircraft documents organized by collection
        GET /api/aircraft/{id}/documents/

        Returns:
        - collections: List of document collections with their documents
        - uncollected_documents: Documents not in any collection
        """
        aircraft = self.get_object()

        # Get all collections for this aircraft with their documents
        collections = aircraft.doc_collections.prefetch_related('documents__images').all()

        # Get documents not in any collection
        uncollected_documents = aircraft.documents.filter(
            collection__isnull=True
        ).prefetch_related('images')

        return Response({
            'collections': DocumentCollectionNestedSerializer(
                collections,
                many=True,
                context={'request': request}
            ).data,
            'uncollected_documents': DocumentNestedSerializer(
                uncollected_documents,
                many=True,
                context={'request': request}
            ).data,
        })

    @action(detail=True, methods=['get', 'post'])
    def squawks(self, request, pk=None):
        """
        Get or create squawks for an aircraft
        GET /api/aircraft/{id}/squawks/ - Get all squawks (active and resolved)
        POST /api/aircraft/{id}/squawks/ - Create a new squawk

        Query params for GET:
        - resolved: true/false (filter by resolved status)
        """
        aircraft = self.get_object()

        if request.method == 'GET':
            squawks = aircraft.squawks.all().order_by('-created_at')

            # Filter by resolved status if specified
            resolved_param = request.query_params.get('resolved')
            if resolved_param is not None:
                resolved = resolved_param.lower() == 'true'
                squawks = squawks.filter(resolved=resolved)

            return Response({
                'squawks': SquawkNestedSerializer(
                    squawks,
                    many=True,
                    context={'request': request}
                ).data,
            })

        elif request.method == 'POST':
            # Create a new squawk for this aircraft
            data = request.data.copy()
            data['aircraft'] = aircraft.id

            # Set reported_by to current user if authenticated
            if request.user.is_authenticated:
                data['reported_by'] = request.user.id

            serializer = SquawkCreateUpdateSerializer(data=data)
            if serializer.is_valid():
                squawk = serializer.save()
                return Response(
                    SquawkNestedSerializer(squawk, context={'request': request}).data,
                    status=status.HTTP_201_CREATED
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get', 'post'])
    def notes(self, request, pk=None):
        """
        Get or create notes for an aircraft
        GET /api/aircraft/{id}/notes/ - Get all notes
        POST /api/aircraft/{id}/notes/ - Create a new note
        """
        aircraft = self.get_object()

        if request.method == 'GET':
            notes = aircraft.notes.all().order_by('-added_timestamp')

            return Response({
                'notes': AircraftNoteNestedSerializer(
                    notes,
                    many=True,
                    context={'request': request}
                ).data,
            })

        elif request.method == 'POST':
            # Create a new note for this aircraft
            data = request.data.copy()
            data['aircraft'] = aircraft.id

            serializer = AircraftNoteCreateUpdateSerializer(data=data)
            if serializer.is_valid():
                # Set added_by to current user if authenticated
                note = serializer.save(
                    added_by=request.user if request.user.is_authenticated else None
                )
                return Response(
                    AircraftNoteNestedSerializer(note, context={'request': request}).data,
                    status=status.HTTP_201_CREATED
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get', 'post'])
    def oil_records(self, request, pk=None):
        """
        Get or create oil records for an aircraft
        GET /api/aircraft/{id}/oil_records/ - Get all oil records
        POST /api/aircraft/{id}/oil_records/ - Create a new oil record
        """
        aircraft = self.get_object()

        if request.method == 'GET':
            records = aircraft.oil_records.all()
            return Response({
                'oil_records': OilRecordNestedSerializer(records, many=True).data,
            })

        elif request.method == 'POST':
            data = request.data.copy()
            data['aircraft'] = aircraft.id
            if 'flight_hours' not in data or not data['flight_hours']:
                data['flight_hours'] = str(aircraft.flight_time)

            serializer = OilRecordCreateSerializer(data=data)
            if serializer.is_valid():
                record = serializer.save()
                return Response(
                    OilRecordNestedSerializer(record).data,
                    status=status.HTTP_201_CREATED
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get', 'post'])
    def fuel_records(self, request, pk=None):
        """
        Get or create fuel records for an aircraft
        GET /api/aircraft/{id}/fuel_records/ - Get all fuel records
        POST /api/aircraft/{id}/fuel_records/ - Create a new fuel record
        """
        aircraft = self.get_object()

        if request.method == 'GET':
            records = aircraft.fuel_records.all()
            return Response({
                'fuel_records': FuelRecordNestedSerializer(records, many=True).data,
            })

        elif request.method == 'POST':
            data = request.data.copy()
            data['aircraft'] = aircraft.id
            if 'flight_hours' not in data or not data['flight_hours']:
                data['flight_hours'] = str(aircraft.flight_time)

            serializer = FuelRecordCreateSerializer(data=data)
            if serializer.is_valid():
                record = serializer.save()
                return Response(
                    FuelRecordNestedSerializer(record).data,
                    status=status.HTTP_201_CREATED
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AircraftNoteViewSet(viewsets.ModelViewSet):
    queryset = AircraftNote.objects.all().order_by('-added_timestamp')
    serializer_class = AircraftNoteSerializer

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return AircraftNoteCreateUpdateSerializer
        return AircraftNoteNestedSerializer

    def perform_update(self, serializer):
        """Set edited_timestamp when note is updated"""
        serializer.save(edited_timestamp=timezone.now())


class AircraftEventViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AircraftEvent.objects.all()
    serializer_class = AircraftSerializer

@require_GET
def healthz(request):
    return JsonResponse({"status": "ok"})


class AircraftDetailView(LoginRequiredMixin, TemplateView):
    template_name = 'aircraft_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['aircraft_id'] = self.kwargs['pk']
        return context


class SquawkHistoryView(LoginRequiredMixin, TemplateView):
    template_name = 'squawk_history.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['aircraft_id'] = self.kwargs['pk']
        return context
