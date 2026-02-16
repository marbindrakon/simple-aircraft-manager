from rest_framework import serializers

from .models import Aircraft, AircraftNote, AircraftEvent, AircraftRole
from health.services import calculate_airworthiness


class AirworthinessMixin:
    def get_airworthiness(self, obj):
        return calculate_airworthiness(obj).to_dict()


class UserRoleMixin:
    """Adds user_role field based on the requesting user's role on the aircraft."""
    def get_user_role(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        if request.user.is_staff or request.user.is_superuser:
            return 'admin'
        for role in obj.roles.all():  # hits prefetch cache
            if role.user_id == request.user.id:
                return role.role
        return None


class AircraftSerializer(AirworthinessMixin, UserRoleMixin, serializers.HyperlinkedModelSerializer):
    airworthiness = serializers.SerializerMethodField()
    user_role = serializers.SerializerMethodField()
    notes = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    events = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    roles = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    share_token = serializers.SerializerMethodField()
    share_url = serializers.SerializerMethodField()

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
                'user_role',
                'public_sharing_enabled',
                'share_token',
                'share_url',
                'notes',
                'squawks',
                'events',
                'roles',
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

    def get_share_token(self, obj):
        """Only visible to owners/admins."""
        role = self.get_user_role(obj)
        if role in ('owner', 'admin'):
            return str(obj.share_token) if obj.share_token else None
        return None

    def get_share_url(self, obj):
        """Only visible to owners/admins."""
        role = self.get_user_role(obj)
        if role in ('owner', 'admin') and obj.share_token and obj.public_sharing_enabled:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(f'/shared/{obj.share_token}/')
        return None


class AircraftListSerializer(AirworthinessMixin, UserRoleMixin, serializers.HyperlinkedModelSerializer):
    airworthiness = serializers.SerializerMethodField()
    user_role = serializers.SerializerMethodField()

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
            'user_role',
            'public_sharing_enabled',
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


class AircraftRoleSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    user_display = serializers.SerializerMethodField()

    class Meta:
        model = AircraftRole
        fields = ['id', 'user', 'username', 'user_display', 'role', 'created_at']
        read_only_fields = ['id', 'created_at']

    def get_user_display(self, obj):
        full = obj.user.get_full_name()
        return full if full else obj.user.username

