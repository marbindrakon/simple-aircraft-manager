from django.http import Http404
from django.shortcuts import render
from django.utils import timezone
from django.views.generic import TemplateView

from core.models import AircraftShareToken


class PublicAircraftView(TemplateView):
    """Read-only public view of an aircraft via share token."""
    template_name = 'aircraft_detail.html'

    def get(self, request, share_token, *args, **kwargs):
        try:
            token_obj = AircraftShareToken.objects.select_related('aircraft').get(token=share_token)
        except AircraftShareToken.DoesNotExist:
            raise Http404
        if token_obj.expires_at and token_obj.expires_at < timezone.now():
            raise Http404
        aircraft = token_obj.aircraft
        return render(request, self.template_name, {
            'aircraft_id': str(aircraft.id),
            'share_token': str(share_token),
            'privilege_level': token_obj.privilege,
            'base_template': 'base_public.html',
        })
