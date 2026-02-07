from core.models import Aircraft, AircraftNote, AircraftEvent
from core.serializers import AircraftSerializer, AircraftNoteSerializer, AircraftEventSerializer, UserSerializer
from health.models import Component, LogbookEntry, Squawk
from health.serializers import ComponentSerializer, LogbookEntrySerializer, SquawkSerializer

from django.contrib.auth.models import User
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from decimal import Decimal


class AircraftViewSet(viewsets.ModelViewSet):
    queryset = Aircraft.objects.all()
    serializer_class = AircraftSerializer

    @action(detail=True, methods=['post'])
    def update_hours(self, request, pk=None):
        """
        Update aircraft hours and automatically sync to all in-service components
        POST /api/aircraft/{id}/update_hours/

        Body: {
            "new_hours": 1234.5
        }
        """
        aircraft = self.get_object()
        new_hours = request.data.get('new_hours')

        # Validation
        if new_hours is None:
            return Response({'error': 'new_hours required'},
                          status=status.HTTP_400_BAD_REQUEST)

        try:
            new_hours = Decimal(str(new_hours))
        except:
            return Response({'error': 'Invalid hours value'},
                          status=status.HTTP_400_BAD_REQUEST)

        if new_hours < aircraft.flight_time:
            return Response({'error': 'Hours cannot decrease'},
                          status=status.HTTP_400_BAD_REQUEST)

        hours_delta = new_hours - aircraft.flight_time
        old_hours = aircraft.flight_time

        # Update aircraft
        aircraft.flight_time = new_hours
        aircraft.save()

        # ALWAYS update all in-service components (not optional)
        components = aircraft.components.filter(status='IN-USE')
        updated_components = []
        for component in components:
            component.hours_in_service += hours_delta
            component.hours_since_overhaul += hours_delta
            component.save()
            updated_components.append(str(component.id))

        return Response({
            'success': True,
            'aircraft_hours': float(aircraft.flight_time),
            'hours_added': float(hours_delta),
            'components_updated': len(updated_components),
        })

    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        """
        Get aircraft summary with components, recent logs, active squawks
        GET /api/aircraft/{id}/summary/
        """
        aircraft = self.get_object()

        return Response({
            'aircraft': AircraftSerializer(aircraft, context={'request': request}).data,
            'components': ComponentSerializer(
                aircraft.components.all(),
                many=True,
                context={'request': request}
            ).data,
            'recent_logs': LogbookEntrySerializer(
                aircraft.logbook_entries.order_by('-date')[:10],
                many=True,
                context={'request': request}
            ).data,
            'active_squawks': SquawkSerializer(
                aircraft.squawks.filter(resolved=False),
                many=True,
                context={'request': request}
            ).data,
        })


class AircraftNoteViewSet(viewsets.ModelViewSet):
    queryset = AircraftNote.objects.all()
    serializer_class = AircraftNoteSerializer


class AircraftEventViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AircraftEvent.objects.all()
    serializer_class = AircraftSerializer

class UserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer


class AircraftDetailView(LoginRequiredMixin, TemplateView):
    template_name = 'aircraft_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['aircraft_id'] = self.kwargs['pk']
        return context
