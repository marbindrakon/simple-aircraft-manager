from rest_framework import serializers

from .models import ComponentType, Component, DocumentCollection, Document, DocumentImage, LogbookEntry, Squawk, InspectionType, AD, STCApplication, InspectionRecord, ADCompliance, OilRecord, FuelRecord

class ComponentTypeSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = ComponentType
        fields = '__all__'

class ComponentSerializer(serializers.HyperlinkedModelSerializer):
    component_type_name = serializers.CharField(source='component_type.name', read_only=True)

    class Meta:
        model = Component
        fields = [
                'id',
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


class SquawkNestedSerializer(serializers.ModelSerializer):
    """Nested serializer for squawks with display fields"""
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    component_name = serializers.SerializerMethodField()
    reported_by_username = serializers.CharField(source='reported_by.username', read_only=True, default=None)

    class Meta:
        model = Squawk
        fields = [
            'id',
            'aircraft',
            'component',
            'component_name',
            'priority',
            'priority_display',
            'issue_reported',
            'attachment',
            'created_at',
            'reported_by',
            'reported_by_username',
            'resolved',
            'notes',
        ]

    def get_component_name(self, obj):
        if obj.component:
            return str(obj.component.component_type.name)
        return None


class SquawkCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating squawks"""
    class Meta:
        model = Squawk
        fields = [
            'id',
            'aircraft',
            'component',
            'priority',
            'issue_reported',
            'attachment',
            'resolved',
            'notes',
        ]
        read_only_fields = ['id']

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


class OilRecordNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = OilRecord
        fields = ['id', 'aircraft', 'date', 'quantity_added', 'level_after', 'oil_type', 'flight_hours', 'notes', 'created_at']


class OilRecordCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = OilRecord
        fields = ['id', 'aircraft', 'date', 'quantity_added', 'level_after', 'oil_type', 'flight_hours', 'notes']
        read_only_fields = ['id']


class FuelRecordNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = FuelRecord
        fields = ['id', 'aircraft', 'date', 'quantity_added', 'level_after', 'fuel_type', 'flight_hours', 'notes', 'created_at']


class FuelRecordCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = FuelRecord
        fields = ['id', 'aircraft', 'date', 'quantity_added', 'level_after', 'fuel_type', 'flight_hours', 'notes']
        read_only_fields = ['id']
