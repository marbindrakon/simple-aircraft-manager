from django.contrib.auth.models import User
from rest_framework import serializers

from .models import Aircraft, AircraftNote, AircraftEvent

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'id', 'url']

class AircraftSerializer(serializers.HyperlinkedModelSerializer):
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

