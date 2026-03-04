"""Shared token validation helper used by public views."""
from django.http import JsonResponse
from django.utils import timezone

from core.models import AircraftShareToken


def validate_share_token(share_token):
    """
    Validate a share token UUID.
    Returns (token_obj, None) on success or (None, error_json_response) on failure.
    """
    try:
        token_obj = AircraftShareToken.objects.select_related('aircraft').get(token=share_token)
    except AircraftShareToken.DoesNotExist:
        return None, JsonResponse({'error': 'Not found'}, status=404)
    if token_obj.expires_at and token_obj.expires_at < timezone.now():
        return None, JsonResponse({'error': 'Not found'}, status=404)
    return token_obj, None
