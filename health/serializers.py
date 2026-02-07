from rest_framework import serializers

from .models import ComponentType, Component, DocumentCollection, Document, DocumentImage, LogbookEntry, Squawk, InspectionType, AD, STCApplication, InspectionRecord, ADCompliance

class ComponentTypeSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = ComponentType
        fields = '__all__'

class ComponentSerializer(serializers.HyperlinkedModelSerializer):
    component_type_name = serializers.CharField(source='component_type.name', read_only=True)

    class Meta:
        model = Component
        fields = [
                'aircraft',
                'parent_component',
                'component_type',
                'component_type_name',
                'manufacturer',
                'model',
                'serial_number',
                'install_location',
                'notes',
                'status',
                'date_in_service',
                'hours_in_service',
                'hours_since_overhaul',
                'overhaul_date',
                'tbo_hours',
                'tbo_days',
                'inspection_hours',
                'inspection_days',
                'replacement_hours',
                'replacement_days',
                'tbo_critical',
                'inspection_critical',
                'replacement_critical',
                'components',
                'doc_collections',
                'documents',
                'squawks',
                'applicable_inspections',
                'ads',
                'stcs',
                'inspections',
                'ad_compliance',
                ]

class DocumentImageSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = DocumentImage
        fields = '__all__'


class DocumentImageNestedSerializer(serializers.ModelSerializer):
    """Nested serializer for document images without hyperlinks"""
    class Meta:
        model = DocumentImage
        fields = ['id', 'notes', 'image']


class DocumentNestedSerializer(serializers.ModelSerializer):
    """Nested serializer for documents with images included"""
    images = DocumentImageNestedSerializer(many=True, read_only=True)
    doc_type_display = serializers.CharField(source='get_doc_type_display', read_only=True)

    class Meta:
        model = Document
        fields = [
            'id',
            'name',
            'description',
            'doc_type',
            'doc_type_display',
            'images',
        ]


class DocumentCollectionNestedSerializer(serializers.ModelSerializer):
    """Nested serializer for collections with documents included"""
    documents = DocumentNestedSerializer(many=True, read_only=True)
    document_count = serializers.SerializerMethodField()

    class Meta:
        model = DocumentCollection
        fields = [
            'id',
            'name',
            'description',
            'documents',
            'document_count',
        ]

    def get_document_count(self, obj):
        return obj.documents.count()


class DocumentCollectionSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = DocumentCollection
        fields = [
                'url',
                'id',
                'aircraft',
                'components',
                'name',
                'description',
                'documents',
                ]

class DocumentSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Document
        fields = [
                'url',
                'id',
                'aircraft',
                'components',
                'collection',
                'name',
                'description',
                'related_logs',
                'log_entry',
                'images',
                ]

class LogbookEntrySerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = LogbookEntry
        fields = '__all__'

class SquawkSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Squawk
        fields = '__all__'

class InspectionTypeSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = InspectionType
        fields = '__all__'

class ADSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = AD
        fields = '__all__'

class STCApplicationSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = STCApplication
        fields = '__all__'

class InspectionRecordSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = InspectionRecord
        fields = '__all__'

class ADComplianceSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = ADCompliance
        fields = '__all__'
