import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Prefetch
from django.views.generic import TemplateView
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from core.models import AircraftRole, InvitationCode, InvitationCodeAircraftRole
from core.serializers import (
    InvitationCodeSerializer, InvitationCodeDetailSerializer,
    InvitationCodeAircraftRoleSerializer,
)

logger = logging.getLogger(__name__)

User = get_user_model()

class InvitationCodeViewSet(viewsets.ModelViewSet):
    queryset = InvitationCode.objects.all().order_by('-created_at').prefetch_related(
        'initial_roles__aircraft', 'redemptions__user'
    )
    serializer_class = InvitationCodeSerializer

    def get_permissions(self):
        return [IsAdminUser()]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return InvitationCodeDetailSerializer
        return InvitationCodeSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'], url_path='toggle_active')
    def toggle_active(self, request, pk=None):
        code = self.get_object()
        code.is_active = not code.is_active
        code.save()
        return Response(InvitationCodeSerializer(code, context={'request': request}).data)


class InvitationCodeAircraftRoleViewSet(viewsets.ModelViewSet):
    queryset = InvitationCodeAircraftRole.objects.all()
    serializer_class = InvitationCodeAircraftRoleSerializer

    def get_permissions(self):
        return [IsAdminUser()]

    def list(self, request, *args, **kwargs):
        from rest_framework.exceptions import MethodNotAllowed
        raise MethodNotAllowed('GET')

    def retrieve(self, request, *args, **kwargs):
        from rest_framework.exceptions import MethodNotAllowed
        raise MethodNotAllowed('GET')

    def update(self, request, *args, **kwargs):
        from rest_framework.exceptions import MethodNotAllowed
        raise MethodNotAllowed('PUT')

    def partial_update(self, request, *args, **kwargs):
        from rest_framework.exceptions import MethodNotAllowed
        raise MethodNotAllowed('PATCH')


class ManageInvitationsView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'manage/invitations.html'

    def test_func(self):
        return self.request.user.is_staff


class ManageInvitationDetailView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'manage/invitation_detail.html'

    def test_func(self):
        return self.request.user.is_staff

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['invitation_id'] = str(self.kwargs['pk'])
        return context


class ManageUsersView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'manage/users.html'

    def test_func(self):
        return self.request.user.is_staff

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['users'] = User.objects.all().prefetch_related(
            Prefetch('aircraft_roles', queryset=AircraftRole.objects.select_related('aircraft'))
        ).order_by('username')
        return context
