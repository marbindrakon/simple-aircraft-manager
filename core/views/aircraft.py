import logging
from datetime import timedelta as td

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.action_registry import get_action_permissions
from core.events import log_event
from core.features import feature_available
from core.models import Aircraft, AircraftRole, AircraftShareToken
from core.permissions import (
    get_user_role, has_aircraft_permission, user_can_create_aircraft,
    CanCreateAircraft, IsAircraftOwnerOrAdmin, IsAircraftPilotOrAbove,
)
from core.serializers import (
    AircraftSerializer, AircraftListSerializer,
    AircraftRoleSerializer, AircraftShareTokenSerializer,
)
from health.aircraft_actions import HealthAircraftActionsMixin

logger = logging.getLogger(__name__)

User = get_user_model()

class AircraftViewSet(HealthAircraftActionsMixin, viewsets.ModelViewSet):
    queryset = Aircraft.objects.all()
    serializer_class = AircraftSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated(), CanCreateAircraft()]
        if self.action in ('update', 'partial_update', 'destroy',
                           'manage_roles', 'manage_share_tokens', 'delete_share_token'):
            return [IsAuthenticated(), IsAircraftOwnerOrAdmin()]
        # Registry covers all health + plugin actions
        found, perms = get_action_permissions(self.action, self.request.method)
        if found:
            return [IsAuthenticated()] + perms
        # list, retrieve, and any unknown actions
        return [IsAuthenticated(), IsAircraftPilotOrAbove()]

    def get_queryset(self):
        qs = super().get_queryset().prefetch_related('roles')
        user = self.request.user
        if not user.is_authenticated:
            return qs.none()
        if user.is_staff or user.is_superuser:
            return qs
        accessible = AircraftRole.objects.filter(user=user).values_list('aircraft_id', flat=True)
        return qs.filter(id__in=accessible)

    def get_serializer_class(self):
        """Use lightweight serializer for list, full serializer for detail."""
        if self.action == 'list':
            return AircraftListSerializer
        return AircraftSerializer

    def perform_create(self, serializer):
        max_aircraft = settings.SAM_MAX_AIRCRAFT
        with transaction.atomic():
            if max_aircraft is not None:
                # select_for_update() serialises concurrent creates on PostgreSQL,
                # preventing the TOCTOU window between the count read and the insert.
                current_count = Aircraft.objects.select_for_update().count()
                if current_count >= max_aircraft:
                    raise PermissionDenied(
                        detail=f"Aircraft limit reached ({current_count}/{max_aircraft}). "
                        "Contact your administrator to increase your quota."
                    )
            aircraft = serializer.save()
            AircraftRole.objects.create(aircraft=aircraft, user=self.request.user, role='owner')
        log_event(aircraft, 'aircraft', 'Aircraft created', user=self.request.user)

    @action(detail=True, methods=['get', 'post', 'delete'], url_path='manage_roles')
    def manage_roles(self, request, pk=None):
        """
        List, add/update, or remove role assignments.
        GET  - List all roles
        POST - Add or update a role: {user: <user_id>, role: 'owner'|'pilot'}
        DELETE - Remove a role: {user: <user_id>}
        """
        aircraft = self.get_object()

        if request.method == 'GET':
            roles = AircraftRole.objects.filter(aircraft=aircraft).select_related('user')
            return Response({
                'roles': AircraftRoleSerializer(roles, many=True).data,
            })

        if request.method == 'POST':
            user_id = request.data.get('user')
            role = request.data.get('role')
            if not user_id or role not in ('owner', 'pilot'):
                return Response({'error': 'Valid user and role required.'},
                                status=status.HTTP_400_BAD_REQUEST)
            try:
                target_user = User.objects.get(pk=user_id)
            except (User.DoesNotExist, ValueError):
                # Uniform error to prevent user enumeration
                return Response({'error': 'Valid user and role required.'},
                                status=status.HTTP_400_BAD_REQUEST)

            existing = AircraftRole.objects.filter(aircraft=aircraft, user=target_user).first()
            if existing:
                # Changing role
                if existing.role == 'owner' and role == 'pilot':
                    # Demoting owner — check last-owner protection
                    if not request.user.is_staff:
                        owner_count = AircraftRole.objects.filter(
                            aircraft=aircraft, role='owner').count()
                        if owner_count <= 1:
                            return Response(
                                {'error': 'Cannot demote the last owner.'},
                                status=status.HTTP_400_BAD_REQUEST)
                existing.role = role
                existing.save()
                log_event(aircraft, 'role',
                          f"Role updated: {role} for {target_user.username}",
                          user=request.user,
                          notes=f"by {request.user.username}")
            else:
                AircraftRole.objects.create(aircraft=aircraft, user=target_user, role=role)
                log_event(aircraft, 'role',
                          f"Role granted: {role} to {target_user.username}",
                          user=request.user,
                          notes=f"by {request.user.username}")

            roles = AircraftRole.objects.filter(aircraft=aircraft).select_related('user')
            return Response({
                'roles': AircraftRoleSerializer(roles, many=True).data,
            })

        if request.method == 'DELETE':
            user_id = request.data.get('user')
            if not user_id:
                return Response({'error': 'user is required.'},
                                status=status.HTTP_400_BAD_REQUEST)
            try:
                role_obj = AircraftRole.objects.select_related('user').get(
                    aircraft=aircraft, user_id=user_id)
            except (AircraftRole.DoesNotExist, ValueError):
                return Response({'error': 'Role not found.'},
                                status=status.HTTP_404_NOT_FOUND)

            # Self-removal prevention (non-admin)
            if role_obj.user == request.user and not request.user.is_staff:
                return Response({'error': 'Cannot remove your own role.'},
                                status=status.HTTP_400_BAD_REQUEST)

            # Last-owner protection (non-admin)
            if role_obj.role == 'owner' and not request.user.is_staff:
                owner_count = AircraftRole.objects.filter(
                    aircraft=aircraft, role='owner').count()
                if owner_count <= 1:
                    return Response({'error': 'Cannot remove the last owner.'},
                                    status=status.HTTP_400_BAD_REQUEST)

            target_username = role_obj.user.username
            role_obj.delete()
            log_event(aircraft, 'role',
                      f"Role removed: {target_username}",
                      user=request.user,
                      notes=f"by {request.user.username}")

            roles = AircraftRole.objects.filter(aircraft=aircraft).select_related('user')
            return Response({
                'roles': AircraftRoleSerializer(roles, many=True).data,
            })

    @action(detail=True, methods=['get', 'post'], url_path='share_tokens')
    def manage_share_tokens(self, request, pk=None):
        """
        List or create share tokens for an aircraft.
        GET  /api/aircraft/{id}/share_tokens/ - List all tokens
        POST /api/aircraft/{id}/share_tokens/ - Create a new token
        """
        aircraft = self.get_object()

        if request.method == 'GET':
            tokens = aircraft.share_tokens.all()
            return Response(
                AircraftShareTokenSerializer(tokens, many=True, context={'request': request}).data
            )

        # POST: check sharing feature is enabled
        if not feature_available('sharing', aircraft):
            return Response(
                {'error': 'Sharing is disabled for this aircraft.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # POST: create a new token
        privilege = request.data.get('privilege')
        if privilege not in ('status', 'maintenance'):
            return Response(
                {'error': 'privilege must be "status" or "maintenance".'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        label = request.data.get('label', '').strip()
        expires_at = None
        expires_in_days = request.data.get('expires_in_days')
        if expires_in_days is not None:
            try:
                days = int(expires_in_days)
            except (ValueError, TypeError):
                return Response({'error': 'expires_in_days must be an integer.'},
                                status=status.HTTP_400_BAD_REQUEST)
            if not (1 <= days <= 3650):
                return Response({'error': 'expires_in_days must be between 1 and 3650.'},
                                status=status.HTTP_400_BAD_REQUEST)
            expires_at = timezone.now() + td(days=days)

        with transaction.atomic():
            token_count = aircraft.share_tokens.select_for_update().count()
            if token_count >= 10:
                return Response(
                    {'error': 'Maximum of 10 share links per aircraft.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            token_obj = AircraftShareToken.objects.create(
                aircraft=aircraft,
                label=label,
                privilege=privilege,
                expires_at=expires_at,
                created_by=request.user,
            )
        log_event(
            aircraft, 'role',
            f"Share link created: {label or privilege}",
            user=request.user,
        )
        return Response(
            AircraftShareTokenSerializer(token_obj, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['delete'],
            url_path=r'share_tokens/(?P<token_id>[^/.]+)')
    def delete_share_token(self, request, pk=None, token_id=None):
        """
        Delete a share token.
        DELETE /api/aircraft/{id}/share_tokens/{token_id}/
        """
        aircraft = self.get_object()
        try:
            token_obj = AircraftShareToken.objects.get(id=token_id, aircraft=aircraft)
        except (AircraftShareToken.DoesNotExist, ValueError):
            return Response({'error': 'Share token not found.'}, status=status.HTTP_404_NOT_FOUND)

        label = token_obj.label or token_obj.privilege
        token_obj.delete()
        log_event(aircraft, 'role', f"Share link revoked: {label}", user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


