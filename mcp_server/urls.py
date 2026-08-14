"""
URL patterns for the MCP endpoint and the root .well-known OAuth metadata.

Included from the project urls.py only when settings.MCP_ENABLED is true. The
oauth2_provider AS routes themselves are mounted under /o/ (which registers the
'oauth2_provider' namespace the metadata views reverse against); the RFC 8414 /
RFC 9728 documents must additionally live at the server root, so the DOT
metadata views are re-mounted here without a namespace.
"""
from django.urls import path

from oauth2_provider.views import (
    OAuthProtectedResourceMetadataView, OAuthServerMetadataView,
)

from mcp_server.views import McpEndpointView

urlpatterns = [
    # Canonical MCP endpoint (advertised without trailing slash); both forms work.
    path('mcp', McpEndpointView.as_view(), name='mcp-endpoint'),
    path('mcp/', McpEndpointView.as_view()),
    # RFC 8414 authorization server metadata (root + issuer-path form).
    path('.well-known/oauth-authorization-server', OAuthServerMetadataView.as_view()),
    path('.well-known/oauth-authorization-server/<path:issuer_path>', OAuthServerMetadataView.as_view()),
    # RFC 9728 protected resource metadata (root + resource-path form, e.g. /mcp).
    path('.well-known/oauth-protected-resource', OAuthProtectedResourceMetadataView.as_view()),
    path('.well-known/oauth-protected-resource/<path:resource_path>', OAuthProtectedResourceMetadataView.as_view()),
]
