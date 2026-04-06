"""Views for the Weight & Balance plugin.

ViewSets: WBConfigViewSet, WBCalculationViewSet
Page view: WBConfigListView (management page at /wb/)
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from rest_framework import viewsets

from core.mixins import AircraftScopedMixin, EventLoggingMixin

from .models import WBConfig, WBCalculation
from .serializers import WBConfigSerializer, WBCalculationSerializer


class WBConfigViewSet(AircraftScopedMixin, EventLoggingMixin, viewsets.ModelViewSet):
    """CRUD for per-aircraft W&B envelope configurations.

    Scoped to the requesting user's accessible aircraft by AircraftScopedMixin.
    Supports ?aircraft=<uuid> query param to filter to a single aircraft.
    Write operations require owner-level access (enforced by AircraftScopedMixin).
    """

    serializer_class = WBConfigSerializer
    aircraft_fk_path = 'aircraft'
    event_category = 'wb_config'
    queryset = WBConfig.objects.select_related('aircraft')

    def get_queryset(self):
        qs = super().get_queryset()
        aircraft_id = self.request.query_params.get('aircraft')
        if aircraft_id:
            qs = qs.filter(aircraft_id=aircraft_id)
        return qs


class WBCalculationViewSet(AircraftScopedMixin, EventLoggingMixin, viewsets.ModelViewSet):
    """CRUD for saved W&B loading scenarios.

    Scoped to the requesting user's accessible aircraft by AircraftScopedMixin.
    Supports ?aircraft=<uuid> query param to filter to a single aircraft.
    Write operations require owner-level access (enforced by AircraftScopedMixin).
    """

    serializer_class = WBCalculationSerializer
    aircraft_fk_path = 'aircraft'
    event_category = 'wb_calc'
    queryset = WBCalculation.objects.select_related('aircraft')

    def get_queryset(self):
        qs = super().get_queryset()
        aircraft_id = self.request.query_params.get('aircraft')
        if aircraft_id:
            qs = qs.filter(aircraft_id=aircraft_id)
        return qs


class WBConfigListView(LoginRequiredMixin, TemplateView):
    """Management page: fleet-level list of W&B configuration status.

    Accessible at /wb/ — listed in nav_items and management_views in apps.py.
    Shows every aircraft the logged-in user can access, and whether a W&B
    config has been set up for each one.  Staff users see the full fleet.
    """

    template_name = 'sam_wb_plugin/wb_config_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        if user.is_staff or user.is_superuser:
            from core.models import Aircraft
            aircraft_qs = Aircraft.objects.all().order_by('tail_number')
        else:
            from core.models import AircraftRole
            aircraft_qs = [
                role.aircraft
                for role in (
                    AircraftRole.objects
                    .filter(user=user)
                    .select_related('aircraft')
                    .order_by('aircraft__tail_number')
                )
            ]

        aircraft_ids = [a.id for a in aircraft_qs]
        config_map = {
            cfg.aircraft_id: cfg
            for cfg in WBConfig.objects.filter(aircraft_id__in=aircraft_ids)
        }
        calc_count_map = {}
        for calc in WBCalculation.objects.filter(aircraft_id__in=aircraft_ids).values('aircraft_id'):
            calc_count_map[calc['aircraft_id']] = calc_count_map.get(calc['aircraft_id'], 0) + 1

        context['aircraft_rows'] = [
            {
                'aircraft': aircraft,
                'config': config_map.get(aircraft.id),
                'calc_count': calc_count_map.get(aircraft.id, 0),
            }
            for aircraft in aircraft_qs
        ]
        context['configured_count'] = sum(1 for r in context['aircraft_rows'] if r['config'])
        context['total_count'] = len(context['aircraft_rows'])
        return context
