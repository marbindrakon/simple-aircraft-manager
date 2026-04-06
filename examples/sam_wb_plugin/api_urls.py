"""DRF router registrations for the Weight & Balance plugin.

SAM's main urls.py discovers ROUTER_REGISTRATIONS from this file when the
plugin declares api_url_prefix in its AppConfig.  Each entry is a
(prefix, viewset_class, basename) tuple — same format as core/urls.py.

Registered endpoints:
  GET/POST   /api/wb-configs/
  GET/PUT/PATCH/DELETE /api/wb-configs/{id}/
  GET/POST   /api/wb-calculations/
  GET/PUT/PATCH/DELETE /api/wb-calculations/{id}/
"""

from .views import WBConfigViewSet, WBCalculationViewSet

ROUTER_REGISTRATIONS = [
    ('wb-configs', WBConfigViewSet, {'basename': 'wb-config'}),
    ('wb-calculations', WBCalculationViewSet, {'basename': 'wb-calculation'}),
]
