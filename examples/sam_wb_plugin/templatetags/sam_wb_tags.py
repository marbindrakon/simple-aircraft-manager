"""Template tags for the Weight & Balance plugin.

Usage in templates:
    {% load sam_wb_tags %}
    {% wb_fleet_summary request.user as summary %}
    {{ summary.configured_count }} / {{ summary.total_count }} configured
"""

from django import template
from django.core.cache import cache

register = template.Library()


@register.simple_tag
def wb_fleet_summary(user):
    """Return a dict summarising W&B configuration status across the fleet.

    Keys:
        configured_count  — number of aircraft with a WBConfig
        total_count       — total accessible aircraft
        calc_count        — total saved WBCalculation records
        unconfigured      — list of Aircraft objects without a WBConfig

    Results are cached per-user for 60 seconds to avoid running 3 DB queries
    on every dashboard page load.
    """
    cache_key = f'wb_fleet_summary_{user.id}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    from sam_wb_plugin.models import WBConfig, WBCalculation
    from core.models import Aircraft, AircraftRole

    if user.is_staff or user.is_superuser:
        aircraft_list = list(Aircraft.objects.order_by('tail_number'))
    else:
        aircraft_list = [
            role.aircraft
            for role in (
                AircraftRole.objects
                .filter(user=user)
                .select_related('aircraft')
                .order_by('aircraft__tail_number')
            )
        ]

    aircraft_ids = [a.id for a in aircraft_list]
    configured_ids = set(
        WBConfig.objects
        .filter(aircraft_id__in=aircraft_ids)
        .values_list('aircraft_id', flat=True)
    )
    calc_count = WBCalculation.objects.filter(aircraft_id__in=aircraft_ids).count()

    result = {
        'configured_count': len(configured_ids),
        'total_count': len(aircraft_list),
        'calc_count': calc_count,
        'unconfigured': [a for a in aircraft_list if a.id not in configured_ids],
    }
    cache.set(cache_key, result, 60)
    return result
