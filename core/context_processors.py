"""
Context processors for making settings available in templates.
"""

from django.conf import settings


def oidc_settings(request):
    """
    Make OIDC_ENABLED setting available in all templates.

    Returns:
        dict: Context dictionary with OIDC_ENABLED boolean
    """
    return {
        'OIDC_ENABLED': getattr(settings, 'OIDC_ENABLED', False)
    }


def user_role_context(request):
    """
    Expose whether the current user is an owner of any aircraft.
    Used to conditionally show owner-only navigation items (e.g. Tools).
    """
    user_is_owner = False
    if request.user.is_authenticated:
        if request.user.is_staff or request.user.is_superuser:
            user_is_owner = True
        else:
            from core.models import AircraftRole
            user_is_owner = AircraftRole.objects.filter(
                user=request.user, role='owner'
            ).exists()
    return {'user_is_owner': user_is_owner}
