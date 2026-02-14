from rest_framework import serializers

from .models import ComponentType, Component, DocumentCollection, Document, DocumentImage, LogbookEntry, Squawk, InspectionType, AD, STCApplication, InspectionRecord, ADCompliance, OilRecord, FuelRecord

class ComponentTypeSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = ComponentType
        fields = ['url', 'id', 'name', 'consumable']

class ComponentSerializer(serializers.HyperlinkedModelSerializer):
    component_type_name = serializers.CharField(source='component_type.name', read_only=True)
    component_type_id = serializers.UUIDField(source='component_type.id', read_only=True)
    parent_component_id = serializers.UUIDField(source='parent_component.id', read_only=True, default=None)
    parent_component_name = serializers.SerializerMethodField()

    class Meta:
        model = Component
        fields = [
                'id',
                'aircraft',
                'parent_component',
                'parent_component_id',
                'parent_component_name',
                'component_type',
                'component_type_id',
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

    def get_parent_component_name(self, obj):
        if obj.parent_component:
            name = obj.parent_component.component_type.name
            if obj.parent_component.install_location:
                name += f" ({obj.parent_component.install_location})"
            return name
        return None


class DocumentImageSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.UUIDField(read_only=True)
    ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.pdf', '.txt'}
    ALLOWED_CONTENT_TYPES = {
        'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/bmp', 'image/tiff',
        'application/pdf', 'text/plain',
    }

    class Meta:
        model = DocumentImage
        fields = '__all__'

    def validate_image(self, value):
        import os
        ext = os.path.splitext(value.name)[1].lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            raise serializers.ValidationError(
                f"File type '{ext}' is not allowed. Allowed types: {', '.join(sorted(self.ALLOWED_EXTENSIONS))}"
            )
        if value.content_type not in self.ALLOWED_CONTENT_TYPES:
            raise serializers.ValidationError(
                f"Content type '{value.content_type}' is not allowed."
            )
        return value


class DocumentImageNestedSerializer(serializers.ModelSerializer):
    """Nested serializer for document images without hyperlinks"""
    class Meta:
        model = DocumentImage
        fields = ['id', 'notes', 'image']


class DocumentNestedSerializer(serializers.ModelSerializer):
    """Nested serializer for documents with images included"""
    images = DocumentImageNestedSerializer(many=True, read_only=True)
    doc_type_display = serializers.CharField(source='get_doc_type_display', read_only=True)
    collection_id = serializers.PrimaryKeyRelatedField(source='collection', read_only=True)

    class Meta:
        model = Document
        fields = [
            'id',
            'name',
            'description',
            'doc_type',
            'doc_type_display',
            'collection_id',
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
        read_only_fields = ['documents']

class DocumentSerializer(serializers.HyperlinkedModelSerializer):
    images = DocumentImageNestedSerializer(many=True, read_only=True)
    doc_type_display = serializers.CharField(source='get_doc_type_display', read_only=True)

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
                'doc_type',
                'doc_type_display',
                'related_logs',
                'log_entry',
                'images',
                ]
        read_only_fields = ['images', 'related_logs', 'log_entry', 'doc_type_display']

class LogbookEntrySerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.UUIDField(read_only=True)

    class Meta:
        model = LogbookEntry
        fields = '__all__'

class SquawkSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.UUIDField(read_only=True)

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

    ALLOWED_ATTACHMENT_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.pdf', '.txt'}
    ALLOWED_ATTACHMENT_CONTENT_TYPES = {
        'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/bmp', 'image/tiff',
        'application/pdf', 'text/plain',
    }

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

    def validate_attachment(self, value):
        import os
        ext = os.path.splitext(value.name)[1].lower()
        if ext not in self.ALLOWED_ATTACHMENT_EXTENSIONS:
            raise serializers.ValidationError(
                f"File type '{ext}' is not allowed. Allowed types: {', '.join(sorted(self.ALLOWED_ATTACHMENT_EXTENSIONS))}"
            )
        if value.content_type not in self.ALLOWED_ATTACHMENT_CONTENT_TYPES:
            raise serializers.ValidationError(
                f"Content type '{value.content_type}' is not allowed."
            )
        return value

class InspectionTypeSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.UUIDField(read_only=True)

    class Meta:
        model = InspectionType
        fields = '__all__'


class InspectionTypeNestedSerializer(serializers.ModelSerializer):
    """Nested serializer for InspectionTypes without hyperlinks, used in aircraft detail."""
    class Meta:
        model = InspectionType
        fields = [
            'id', 'name', 'recurring', 'required',
            'recurring_hours', 'recurring_days', 'recurring_months',
        ]


class InspectionRecordNestedSerializer(serializers.ModelSerializer):
    """Nested serializer for InspectionRecord, used in aircraft detail."""
    class Meta:
        model = InspectionRecord
        fields = [
            'id', 'date', 'aircraft_hours', 'inspection_type', 'aircraft', 'logbook_entry',
        ]


class InspectionRecordCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating InspectionRecord."""
    class Meta:
        model = InspectionRecord
        fields = [
            'id', 'date', 'aircraft_hours', 'inspection_type', 'aircraft', 'logbook_entry',
        ]
        read_only_fields = ['id']

class ADSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = AD
        fields = [
            'id', 'url', 'name', 'short_description', 'required_action',
            'compliance_type', 'trigger_condition',
            'recurring', 'recurring_hours', 'recurring_months', 'recurring_days',
            'on_inspection_type', 'applicable_aircraft', 'applicable_component',
        ]


class ADNestedSerializer(serializers.ModelSerializer):
    """Nested serializer for ADs without hyperlinks, used in aircraft detail."""
    class Meta:
        model = AD
        fields = [
            'id', 'name', 'short_description', 'required_action',
            'compliance_type', 'trigger_condition',
            'recurring', 'recurring_hours', 'recurring_months', 'recurring_days',
        ]


class ADComplianceNestedSerializer(serializers.ModelSerializer):
    """Nested serializer for AD compliance records."""
    class Meta:
        model = ADCompliance
        fields = [
            'id', 'ad', 'date_complied', 'compliance_notes',
            'permanent', 'next_due_at_time', 'aircraft_hours_at_compliance',
            'aircraft', 'component', 'logbook_entry',
        ]


class ADComplianceCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating AD compliance records."""
    class Meta:
        model = ADCompliance
        fields = [
            'id', 'ad', 'date_complied', 'compliance_notes',
            'permanent', 'next_due_at_time', 'aircraft_hours_at_compliance',
            'aircraft', 'component', 'logbook_entry',
        ]
        read_only_fields = ['id']

class STCApplicationSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.UUIDField(read_only=True)

    class Meta:
        model = STCApplication
        fields = '__all__'

class InspectionRecordSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.UUIDField(read_only=True)

    class Meta:
        model = InspectionRecord
        fields = '__all__'

class ADComplianceSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.UUIDField(read_only=True)

    class Meta:
        model = ADCompliance
        fields = '__all__'


class ComponentCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating components"""

    class Meta:
        model = Component
        fields = [
            'id',
            'parent_component',
            'component_type',
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
        ]
        read_only_fields = ['id']


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
