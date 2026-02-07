from health.models import *
from health.serializers import *

from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend

class ComponentTypeViewSet(viewsets.ModelViewSet):
    queryset = ComponentType.objects.all()
    serializer_class = ComponentTypeSerializer

class ComponentViewSet(viewsets.ModelViewSet):
    queryset = Component.objects.all()
    serializer_class = ComponentSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['aircraft', 'component_type', 'status']

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
