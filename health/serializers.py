import os

from rest_framework import serializers

from .models import ComponentType, Component, DocumentCollection, Document, DocumentImage, LogbookEntry, Squawk, InspectionType, AD, MajorRepairAlteration, InspectionRecord, ADCompliance, ConsumableRecord

ALLOWED_UPLOAD_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.pdf', '.txt'}
ALLOWED_UPLOAD_CONTENT_TYPES = {
    'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/bmp', 'image/tiff',
    'application/pdf', 'text/plain',
}
MAX_UPLOAD_SIZE = 512 * 1024 * 1024  # 512 MB


def validate_uploaded_file(value):
    if value.size > MAX_UPLOAD_SIZE:
        raise serializers.ValidationError("File size exceeds the 512 MB limit.")
    ext = os.path.splitext(value.name)[1].lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise serializers.ValidationError(
            f"File type '{ext}' is not allowed. Allowed types: {', '.join(sorted(ALLOWED_UPLOAD_EXTENSIONS))}"
        )
    if value.content_type not in ALLOWED_UPLOAD_CONTENT_TYPES:
        raise serializers.ValidationError(
            f"Content type '{value.content_type}' is not allowed."
        )
    return value

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

    class Meta:
        model = DocumentImage
        fields = '__all__'

    def validate_image(self, value):
        return validate_uploaded_file(value)


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
            'visibility',
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
            'visibility',
            'starred',
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
                'visibility',
                'starred',
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
                'visibility',
                'related_logs',
                'log_entry',
                'images',
                ]
        read_only_fields = ['images', 'related_logs', 'log_entry', 'doc_type_display']

class LogbookEntrySerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.UUIDField(read_only=True)
    related_documents_detail = DocumentNestedSerializer(
        source='related_documents', many=True, read_only=True
    )
    log_image_detail = DocumentNestedSerializer(source='log_image', read_only=True)

    class Meta:
        model = LogbookEntry
        fields = [
            'url', 'id', 'log_type', 'aircraft', 'component', 'date', 'text',
            'signoff_person', 'signoff_location', 'log_image', 'log_image_detail',
            'related_documents', 'related_documents_detail',
            'aircraft_hours_at_entry', 'component_hours',
            'entry_type', 'page_number',
        ]
        read_only_fields = ['related_documents_detail', 'log_image_detail']

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
        return validate_uploaded_file(value)

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
    class Meta:
        model = InspectionRecord
        fields = [
            'id', 'date', 'aircraft_hours', 'inspection_type', 'aircraft', 'logbook_entry',
        ]
        read_only_fields = ['id']

class ADSerializer(serializers.HyperlinkedModelSerializer):
    document = DocumentNestedSerializer(read_only=True)
    document_id = serializers.PrimaryKeyRelatedField(
        source='document',
        queryset=Document.objects.all(),
        allow_null=True,
        required=False,
    )

    class Meta:
        model = AD
        fields = [
            'id', 'url', 'name', 'short_description', 'required_action',
            'compliance_type', 'trigger_condition',
            'recurring', 'recurring_hours', 'recurring_months', 'recurring_days',
            'bulletin_type', 'mandatory',
            'document', 'document_id',
            'on_inspection_type', 'applicable_aircraft', 'applicable_component',
        ]
        read_only_fields = ['document']


class ADNestedSerializer(serializers.ModelSerializer):
    """Nested serializer for ADs without hyperlinks, used in aircraft detail."""
    document = DocumentNestedSerializer(read_only=True)

    class Meta:
        model = AD
        fields = [
            'id', 'name', 'short_description', 'required_action',
            'compliance_type', 'trigger_condition',
            'recurring', 'recurring_hours', 'recurring_months', 'recurring_days',
            'bulletin_type', 'mandatory',
            'document',
        ]


class ADComplianceNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = ADCompliance
        fields = [
            'id', 'ad', 'date_complied', 'compliance_notes',
            'permanent', 'next_due_at_time', 'aircraft_hours_at_compliance',
            'aircraft', 'component', 'logbook_entry',
        ]
        read_only_fields = ['id']

class MajorRepairAlterationNestedSerializer(serializers.ModelSerializer):
    record_type_display = serializers.CharField(source='get_record_type_display', read_only=True)
    component_name = serializers.SerializerMethodField()
    form_337_document_name = serializers.CharField(source='form_337_document.name', read_only=True, default=None)
    stc_document_name = serializers.CharField(source='stc_document.name', read_only=True, default=None)
    logbook_entry_date = serializers.DateField(source='logbook_entry.date', read_only=True, default=None)

    class Meta:
        model = MajorRepairAlteration
        fields = [
            'id', 'aircraft', 'record_type', 'record_type_display',
            'title', 'description', 'date_performed', 'performed_by',
            'component', 'component_name',
            'form_337_document', 'form_337_document_name',
            'stc_number', 'stc_holder', 'stc_document', 'stc_document_name',
            'logbook_entry', 'logbook_entry_date',
            'aircraft_hours', 'has_ica', 'ica_notes', 'notes', 'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'record_type_display', 'component_name',
                            'form_337_document_name', 'stc_document_name', 'logbook_entry_date']

    def get_component_name(self, obj):
        if obj.component:
            name = obj.component.component_type.name
            if obj.component.install_location:
                name += f" ({obj.component.install_location})"
            return name
        return None

    def validate(self, data):
        # For creates, aircraft is injected into data by the view before validation.
        # For PATCH updates it won't be present, so fall back to the existing instance.
        aircraft = data.get('aircraft') or (self.instance.aircraft if self.instance else None)
        if not aircraft:
            return data

        errors = {}

        if 'component' in data and data['component'] is not None:
            if data['component'].aircraft_id != aircraft.id:
                errors['component'] = 'Component does not belong to this aircraft.'

        if 'form_337_document' in data and data['form_337_document'] is not None:
            if data['form_337_document'].aircraft_id != aircraft.id:
                errors['form_337_document'] = 'Document does not belong to this aircraft.'

        if 'stc_document' in data and data['stc_document'] is not None:
            if data['stc_document'].aircraft_id != aircraft.id:
                errors['stc_document'] = 'Document does not belong to this aircraft.'

        if 'logbook_entry' in data and data['logbook_entry'] is not None:
            if data['logbook_entry'].aircraft_id != aircraft.id:
                errors['logbook_entry'] = 'Logbook entry does not belong to this aircraft.'

        if errors:
            raise serializers.ValidationError(errors)

        return data

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


class ConsumableRecordNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConsumableRecord
        fields = ['id', 'record_type', 'aircraft', 'date', 'quantity_added', 'level_after', 'consumable_type', 'flight_hours', 'notes', 'created_at']


class ConsumableRecordCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConsumableRecord
        fields = ['id', 'record_type', 'aircraft', 'date', 'quantity_added', 'level_after', 'consumable_type', 'flight_hours', 'notes']
        read_only_fields = ['id']
