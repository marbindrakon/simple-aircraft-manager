"""
Test URLconf with the MCP routes always mounted.

The project urls.py gates the MCP/OAuth routes on settings.MCP_ENABLED at
import time, so tests opt in per-module with
``pytestmark = pytest.mark.urls('tests.mcp.urls')`` instead of toggling the
setting.
"""
from django.conf import settings
from django.urls import include, path

from simple_aircraft_manager.urls import urlpatterns as base_urlpatterns

urlpatterns = list(base_urlpatterns)
if not getattr(settings, 'MCP_ENABLED', False):
    urlpatterns += [
        path('o/', include('oauth2_provider.urls', namespace='oauth2_provider')),
        path('', include('mcp_server.urls')),
    ]
