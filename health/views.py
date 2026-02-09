from health.models import *
from health.serializers import *

from django.utils import timezone
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

class ComponentTypeViewSet(viewsets.ModelViewSet):
    queryset = ComponentType.objects.all()
    serializer_class = ComponentTypeSerializer

class ComponentViewSet(viewsets.ModelViewSet):
    queryset = Component.objects.all()
    serializer_class = ComponentSerializer
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

        # Store old values for response
        old_hours = float(component.hours_in_service)

        # Reset the service counters
        component.hours_in_service = 0
        component.date_in_service = timezone.now().date()
        component.save()

        return Response({
            'success': True,
            'component_id': str(component.id),
            'component_type': component.component_type.name,
            'old_hours': old_hours,
            'new_hours': 0,
            'date_in_service': str(component.date_in_service),
        })

class DocumentCollectionViewSet(viewsets.ModelViewSet):
    queryset = DocumentCollection.objects.all()
    serializer_class = DocumentCollectionSerializer

class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['aircraft', 'doc_type', 'collection']
    search_fields = ['name', 'description']

class DocumentImageViewSet(viewsets.ModelViewSet):
    queryset = DocumentImage.objects.all()
    serializer_class = DocumentImageSerializer

class LogbookEntryViewSet(viewsets.ModelViewSet):
    queryset = LogbookEntry.objects.all().order_by('-date')
    serializer_class = LogbookEntrySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['aircraft', 'log_type', 'entry_type']
    search_fields = ['text', 'signoff_person']

class SquawkViewSet(viewsets.ModelViewSet):
    queryset = Squawk.objects.all().order_by('-created_at')
    serializer_class = SquawkSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['aircraft', 'component', 'priority', 'resolved']
    search_fields = ['issue_reported', 'notes']

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return SquawkCreateUpdateSerializer
        return SquawkSerializer

class InspectionTypeViewSet(viewsets.ModelViewSet):
    queryset = InspectionType.objects.all()
    serializer_class = InspectionTypeSerializer

class ADViewSet(viewsets.ModelViewSet):
    queryset = AD.objects.all()
    serializer_class = ADSerializer

class STCApplicationViewSet(viewsets.ModelViewSet):
    queryset = STCApplication.objects.all()
    serializer_class = STCApplicationSerializer

class InspectionRecordViewSet(viewsets.ModelViewSet):
    queryset = InspectionRecord.objects.all()
    serializer_class = InspectionRecordSerializer

class ADComplianceViewSet(viewsets.ModelViewSet):
    queryset = ADCompliance.objects.all()
    serializer_class = ADComplianceSerializer

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ADComplianceCreateUpdateSerializer
        return ADComplianceSerializer
