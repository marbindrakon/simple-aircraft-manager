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
