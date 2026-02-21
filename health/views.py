from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response


class LogbookPagination(LimitOffsetPagination):
    default_limit = 25
    max_limit = 100

from core.events import log_event
from core.mixins import AircraftScopedMixin, EventLoggingMixin
from health.models import (
    ComponentType, Component, DocumentCollection, Document, DocumentImage,
    LogbookEntry, Squawk, InspectionType, AD, MajorRepairAlteration,
    InspectionRecord, ADCompliance, ConsumableRecord,
)
from health.serializers import (
    ComponentTypeSerializer, ComponentSerializer, ComponentCreateUpdateSerializer,
    DocumentCollectionSerializer, DocumentSerializer, DocumentImageSerializer,
    LogbookEntrySerializer, SquawkSerializer, SquawkCreateUpdateSerializer,
    InspectionTypeSerializer, ADSerializer, MajorRepairAlterationNestedSerializer,
    InspectionRecordSerializer, InspectionRecordNestedSerializer,
    ADComplianceSerializer, ADComplianceNestedSerializer,
    ConsumableRecordNestedSerializer, ConsumableRecordCreateSerializer,
)

class ComponentTypeViewSet(viewsets.ModelViewSet):
    queryset = ComponentType.objects.all()
    serializer_class = ComponentTypeSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdminUser()]
        return [IsAuthenticated()]

class ComponentViewSet(AircraftScopedMixin, EventLoggingMixin, viewsets.ModelViewSet):
    queryset = Component.objects.all()
    serializer_class = ComponentSerializer
    aircraft_fk_path = 'aircraft'
    event_category = 'component'
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['aircraft', 'component_type', 'status']

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ComponentCreateUpdateSerializer
        return ComponentSerializer

    @action(detail=True, methods=['post'])
    def reset_service(self, request, pk=None):
        """
        Reset the service time for a component (e.g., after oil change)
        POST /api/component/{id}/reset_service/

        This resets hours_since_overhaul to 0 and updates overhaul_date to today.
        Typically used for replacement_critical components like oil.
        """
        component = self.get_object()
        reset_in_service = bool(request.data.get('reset_in_service', False))

        # Store old values for response
        old_hours = float(component.hours_since_overhaul)
        old_in_service_hours = float(component.hours_in_service)

        # Always reset OH/SVC time
        component.hours_since_overhaul = 0
        component.overhaul_date = timezone.now().date()

        # Optionally also reset total time in service (for components that are replaced, e.g. oil)
        if reset_in_service:
            component.hours_in_service = 0
            component.date_in_service = timezone.now().date()

        component.save()

        notes = f"Previous OH/SVC hours: {old_hours}"
        if reset_in_service:
            notes += f", previous in-service hours: {old_in_service_hours}"

        log_event(
            component.aircraft, 'component',
            f"Service reset: {component.component_type.name}",
            user=request.user,
            notes=notes,
        )

        return Response({
            'success': True,
            'component_id': str(component.id),
            'component_type': component.component_type.name,
            'old_hours': old_hours,
            'new_hours': 0,
            'reset_in_service': reset_in_service,
            'overhaul_date': str(component.overhaul_date),
        })

class DocumentCollectionViewSet(AircraftScopedMixin, EventLoggingMixin, viewsets.ModelViewSet):
    queryset = DocumentCollection.objects.all()
    serializer_class = DocumentCollectionSerializer
    aircraft_fk_path = 'aircraft'
    event_category = 'document'
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['aircraft']

class DocumentViewSet(AircraftScopedMixin, EventLoggingMixin, viewsets.ModelViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    aircraft_fk_path = 'aircraft'
    event_category = 'document'
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['aircraft', 'doc_type', 'collection']
    search_fields = ['name', 'description']

class DocumentImageViewSet(AircraftScopedMixin, EventLoggingMixin, viewsets.ModelViewSet):
    queryset = DocumentImage.objects.all()
    serializer_class = DocumentImageSerializer
    aircraft_fk_path = 'document__aircraft'
    event_category = 'document'
    aircraft_field = 'document.aircraft'

class LogbookEntryViewSet(AircraftScopedMixin, EventLoggingMixin, viewsets.ModelViewSet):
    queryset = LogbookEntry.objects.all().order_by('-date')
    serializer_class = LogbookEntrySerializer
    aircraft_fk_path = 'aircraft'
    event_category = 'logbook'
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['aircraft', 'log_type', 'entry_type']
    search_fields = ['text', 'signoff_person']
    pagination_class = LogbookPagination

class SquawkViewSet(AircraftScopedMixin, EventLoggingMixin, viewsets.ModelViewSet):
    queryset = Squawk.objects.all().order_by('-created_at')
    serializer_class = SquawkSerializer
    aircraft_fk_path = 'aircraft'
    event_category = 'squawk'
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['aircraft', 'component', 'priority', 'resolved']
    search_fields = ['issue_reported', 'notes']

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return SquawkCreateUpdateSerializer
        return SquawkSerializer

    @action(detail=True, methods=['post'], url_path='link_logbook')
    def link_logbook(self, request, pk=None):
        from django.shortcuts import get_object_or_404
        squawk = self.get_object()
        entry_id = request.data.get('logbook_entry_id')
        resolve = request.data.get('resolve', False)
        if entry_id:
            # Scope to same aircraft to prevent cross-aircraft linking
            entry = get_object_or_404(LogbookEntry, id=entry_id, aircraft=squawk.aircraft)
            squawk.logbook_entries.add(entry)
        if resolve:
            squawk.resolved = True
            squawk.save()
        return Response({'success': True})

class InspectionTypeViewSet(viewsets.ModelViewSet):
    queryset = InspectionType.objects.all()
    serializer_class = InspectionTypeSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdminUser()]
        return [IsAuthenticated()]

class ADViewSet(viewsets.ModelViewSet):
    queryset = AD.objects.all()
    serializer_class = ADSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdminUser()]
        return [IsAuthenticated()]

class MajorRepairAlterationViewSet(AircraftScopedMixin, EventLoggingMixin, viewsets.ModelViewSet):
    queryset = MajorRepairAlteration.objects.all()
    serializer_class = MajorRepairAlterationNestedSerializer
    event_category = 'major_record'
    aircraft_fk_path = 'aircraft'
    event_name_created = 'Major record created'
    event_name_updated = 'Major record updated'
    event_name_deleted = 'Major record deleted'

class InspectionRecordViewSet(AircraftScopedMixin, EventLoggingMixin, viewsets.ModelViewSet):
    queryset = InspectionRecord.objects.all().order_by('-date')
    serializer_class = InspectionRecordSerializer
    aircraft_fk_path = 'aircraft'
    event_category = 'inspection'
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['inspection_type', 'aircraft']

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return InspectionRecordNestedSerializer
        return InspectionRecordSerializer

class ADComplianceViewSet(AircraftScopedMixin, EventLoggingMixin, viewsets.ModelViewSet):
    queryset = ADCompliance.objects.all().order_by('-date_complied')
    serializer_class = ADComplianceSerializer
    aircraft_fk_path = 'aircraft'
    event_category = 'ad'
    event_name_created = 'AD compliance created'
    event_name_updated = 'AD compliance updated'
    event_name_deleted = 'AD compliance deleted'
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['ad', 'aircraft']

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ADComplianceNestedSerializer
        return ADComplianceSerializer


class ConsumableRecordViewSet(AircraftScopedMixin, EventLoggingMixin, viewsets.ModelViewSet):
    queryset = ConsumableRecord.objects.all()
    serializer_class = ConsumableRecordNestedSerializer
    aircraft_fk_path = 'aircraft'
    event_category = 'oil'  # overridden per-record in perform_update/destroy
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['aircraft', 'record_type']

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ConsumableRecordCreateSerializer
        return ConsumableRecordNestedSerializer

    def _event_category(self, instance):
        return instance.record_type  # 'oil' or 'fuel'

    def perform_update(self, serializer):
        instance = serializer.save()
        aircraft = instance.aircraft
        user = self.request.user if hasattr(self, 'request') else None
        label = 'Oil' if instance.record_type == ConsumableRecord.RECORD_TYPE_OIL else 'Fuel'
        log_event(aircraft, instance.record_type, f"{label} record updated", user=user)

    def perform_destroy(self, instance):
        aircraft = instance.aircraft
        user = self.request.user if hasattr(self, 'request') else None
        label = 'Oil' if instance.record_type == ConsumableRecord.RECORD_TYPE_OIL else 'Fuel'
        log_event(aircraft, instance.record_type, f"{label} record deleted", user=user)
        instance.delete()
