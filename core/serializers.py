from rest_framework import serializers
from django.urls import reverse

from .models import Aircraft, AircraftNote, AircraftEvent, AircraftRole, AircraftShareToken, InvitationCode, InvitationCodeAircraftRole, InvitationCodeRedemption
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
    has_share_links = serializers.SerializerMethodField()
    notes = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    events = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    roles = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

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
                'has_share_links',
                'notes',
                'squawks',
                'events',
                'roles',
                'ads',
                'inspections',
                'ad_compliance',
                'components',
                'doc_collections',
                'documents',
                'applicable_inspections'
                ]
        depth = 1

    def get_has_share_links(self, obj):
        """Only visible to owners/admins."""
        role = self.get_user_role(obj)
        if role in ('owner', 'admin'):
            return obj.share_tokens.exists()
        return None


class AircraftListSerializer(AirworthinessMixin, UserRoleMixin, serializers.HyperlinkedModelSerializer):
    airworthiness = serializers.SerializerMethodField()
    user_role = serializers.SerializerMethodField()
    has_share_links = serializers.SerializerMethodField()

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
            'has_share_links',
        ]

    def get_has_share_links(self, obj):
        role = self.get_user_role(obj)
        if role in ('owner', 'admin'):
            return obj.share_tokens.exists()
        return None


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
                'public',
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
            'public',
        ]


class AircraftNoteCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating notes"""
    class Meta:
        model = AircraftNote
        fields = ['id', 'aircraft', 'text', 'public']
        read_only_fields = ['id']


class AircraftShareTokenSerializer(serializers.ModelSerializer):
    share_url = serializers.SerializerMethodField()

    class Meta:
        model = AircraftShareToken
        fields = ['id', 'label', 'privilege', 'expires_at', 'created_at', 'share_url']
        read_only_fields = ['id', 'created_at', 'share_url']

    def get_share_url(self, obj):
        request = self.context.get('request')
        return request.build_absolute_uri(f'/shared/{obj.token}/') if request else None


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


class InvitationCodeAircraftRoleSerializer(serializers.ModelSerializer):
    aircraft_tail_number = serializers.CharField(source='aircraft.tail_number', read_only=True)

    class Meta:
        model = InvitationCodeAircraftRole
        fields = ['id', 'invitation_code', 'aircraft', 'aircraft_tail_number', 'role']
        read_only_fields = ['id', 'aircraft_tail_number']


class InvitationCodeRedemptionSerializer(serializers.ModelSerializer):
    username = serializers.SerializerMethodField()
    user_display = serializers.SerializerMethodField()

    class Meta:
        model = InvitationCodeRedemption
        fields = ['id', 'user', 'username', 'user_display', 'redeemed_at']

    def get_username(self, obj):
        return obj.user.username

    def get_user_display(self, obj):
        return obj.user.get_full_name() or obj.user.username


class InvitationCodeSerializer(serializers.ModelSerializer):
    use_count = serializers.IntegerField(read_only=True)
    created_by_username = serializers.SerializerMethodField()
    is_valid = serializers.SerializerMethodField()
    registration_url = serializers.SerializerMethodField()

    class Meta:
        model = InvitationCode
        fields = [
            'id', 'label', 'invited_email', 'invited_name',
            'max_uses', 'use_count', 'created_by_username',
            'created_at', 'expires_at', 'is_active', 'is_valid',
            'registration_url',
        ]
        read_only_fields = ['id', 'use_count', 'created_by_username', 'created_at', 'is_valid', 'registration_url']

    def get_created_by_username(self, obj):
        return obj.created_by.username if obj.created_by else None

    def get_is_valid(self, obj):
        return obj.is_valid

    def get_registration_url(self, obj):
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(reverse('register', args=[obj.token]))
        return None


class InvitationCodeDetailSerializer(InvitationCodeSerializer):
    initial_roles = InvitationCodeAircraftRoleSerializer(many=True, read_only=True)
    redemptions = InvitationCodeRedemptionSerializer(many=True, read_only=True)

    class Meta(InvitationCodeSerializer.Meta):
        fields = InvitationCodeSerializer.Meta.fields + ['initial_roles', 'redemptions']

