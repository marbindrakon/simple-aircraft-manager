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
    Expose whether the current user is an owner of any aircraft, and whether
    they are permitted to create/import aircraft (per AIRCRAFT_CREATE_PERMISSION).
    """
    user_is_owner = False
    can_create_aircraft = False
    if request.user.is_authenticated:
        if request.user.is_staff or request.user.is_superuser:
            user_is_owner = True
            can_create_aircraft = True
        else:
            from core.models import AircraftRole
            user_is_owner = AircraftRole.objects.filter(
                user=request.user, role='owner'
            ).exists()
            setting = getattr(settings, 'AIRCRAFT_CREATE_PERMISSION', 'any')
            if setting == 'admin':
                can_create_aircraft = False
            elif setting == 'owners':
                can_create_aircraft = user_is_owner
            else:  # 'any'
                can_create_aircraft = True
    return {'user_is_owner': user_is_owner, 'can_create_aircraft': can_create_aircraft}


def theme_context(request):
    pref = request.COOKIES.get('theme_pref', 'system')
    if pref not in ('light', 'dark', 'system'):
        pref = 'system'
    return {
        'theme_pref': pref,
        'html_theme_class': 'pf-v5-theme-dark' if pref == 'dark' else '',
    }
