from rest_framework import serializers

from .models import Aircraft, AircraftNote, AircraftEvent
from health.services import calculate_airworthiness


class AirworthinessMixin:
    def get_airworthiness(self, obj):
        return calculate_airworthiness(obj).to_dict()


class AircraftSerializer(AirworthinessMixin, serializers.HyperlinkedModelSerializer):
    airworthiness = serializers.SerializerMethodField()
    events = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

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


class AircraftListSerializer(AirworthinessMixin, serializers.HyperlinkedModelSerializer):
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
    user_display = serializers.SerializerMethodField()

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
                'user',
                'user_display',
                ]

    def get_user_display(self, obj):
        if not obj.user:
            return None
        full = obj.user.get_full_name()
        return full if full else obj.user.username


class AircraftEventNestedSerializer(serializers.ModelSerializer):
    """Nested serializer for events with display fields."""
    user_display = serializers.SerializerMethodField()

    class Meta:
        model = AircraftEvent
        fields = [
            'id',
            'aircraft',
            'timestamp',
            'category',
            'event_name',
            'notes',
            'user',
            'user_display',
        ]

    def get_user_display(self, obj):
        if not obj.user:
            return None
        full = obj.user.get_full_name()
        return full if full else obj.user.username

