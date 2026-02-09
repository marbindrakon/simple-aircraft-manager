from rest_framework import serializers

from .models import Aircraft, AircraftNote, AircraftEvent
from health.services import calculate_airworthiness


class AircraftSerializer(serializers.HyperlinkedModelSerializer):
    airworthiness = serializers.SerializerMethodField()

    class Meta:
        model = Aircraft
        fields = [
                'url',
                'id',
                'tail_number',
                'make',
                'model',
                'serial_number',
                'description',
                'purchased',
                'added',
                'picture',
                'status',
                'flight_time',
                'airworthiness',
                'notes',
                'squawks',
                'events',
                'ads',
                'stcs',
                'inspections',
                'ad_compliance',
                'components',
                'doc_collections',
                'documents',
                'applicable_inspections'
                ]
        depth = 1

    def get_airworthiness(self, obj):
        """Calculate and return airworthiness status."""
        status = calculate_airworthiness(obj)
        return status.to_dict()


class AircraftListSerializer(serializers.HyperlinkedModelSerializer):
    """Lightweight serializer for aircraft listing with airworthiness status."""
    airworthiness = serializers.SerializerMethodField()

    class Meta:
        model = Aircraft
        fields = [
            'url',
            'id',
            'tail_number',
            'make',
            'model',
            'status',
            'flight_time',
            'picture',
            'airworthiness',
        ]

    def get_airworthiness(self, obj):
        """Calculate and return airworthiness status."""
        status = calculate_airworthiness(obj)
        return status.to_dict()


class AircraftNoteSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = AircraftNote
        fields = [
                'url',
                'id',
                'aircraft',
                'added_timestamp',
                'edited_timestamp',
                'added_by',
                'text',
                ]


class AircraftNoteNestedSerializer(serializers.ModelSerializer):
    """Nested serializer for notes with display fields"""
    added_by_username = serializers.CharField(source='added_by.username', read_only=True, default=None)

    class Meta:
        model = AircraftNote
        fields = [
            'id',
            'aircraft',
            'added_timestamp',
            'edited_timestamp',
            'added_by',
            'added_by_username',
            'text',
        ]


class AircraftNoteCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating notes"""
    class Meta:
        model = AircraftNote
        fields = ['id', 'aircraft', 'text']
        read_only_fields = ['id']


class AircraftEventSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = AircraftEvent
        fields = [
                'url',
                'id',
                'aircraft',
                'timestamp',
                'category',
                'event_name',
                'notes',
                ]

