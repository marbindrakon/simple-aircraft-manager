from core.models import AircraftEvent


def log_event(aircraft, category, event_name, user=None, notes=""):
    """Create an AircraftEvent audit record.

    Called explicitly from views/mixins rather than via signals so we
    have access to request.user and full context.
    """
    AircraftEvent.objects.create(
        aircraft=aircraft,
        category=category,
        event_name=event_name,
        user=user if (user and user.is_authenticated) else None,
        notes=notes,
    )
