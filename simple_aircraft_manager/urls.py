"""
URL configuration for simple_aircraft_manager project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
import importlib

from django.contrib import admin
from django.conf.urls.static import static
from django.conf import settings
from django.urls import path, include
from django.views.generic import RedirectView

from rest_framework import routers

from core import views as core_views
from core.urls import ROUTER_REGISTRATIONS as core_routes
from health.urls import ROUTER_REGISTRATIONS as health_routes
from health.views_public import PublicAircraftSummaryAPI, PublicLogbookEntriesAPI

router = routers.DefaultRouter()
for entry in core_routes + health_routes:
    prefix, viewset = entry[0], entry[1]
    kwargs = entry[2] if len(entry) > 2 else {}
    router.register(prefix, viewset, **kwargs)

# Auto-register API routes from SAM plugins.
# Plugins may provide ROUTER_REGISTRATIONS in their api_urls.py (preferred)
# or urls.py (following the same pattern as core/health).
# Plugins with api_url_prefix set on their AppConfig are scanned automatically.
from django.apps import apps as _django_apps
for _app_config in _django_apps.get_app_configs():
    if not getattr(_app_config, 'sam_plugin', False):
        continue
    # Try api_urls.py first, then fall back to urls.py
    _registered = False
    for _urls_mod_name in (f'{_app_config.name}.api_urls', f'{_app_config.name}.urls'):
        try:
            _plugin_urls = importlib.import_module(_urls_mod_name)
            for _entry in getattr(_plugin_urls, 'ROUTER_REGISTRATIONS', []):
                _prefix, _viewset = _entry[0], _entry[1]
                _kwargs = _entry[2] if len(_entry) > 2 else {}
                router.register(_prefix, _viewset, **_kwargs)
            _registered = True
            break
        except ImportError:
            continue


urlpatterns = [
    path('healthz/', core_views.healthz, name='healthz'),
    path('', RedirectView.as_view(url='/dashboard/', permanent=False), name='home'),
    path('dashboard/', core_views.DashboardView.as_view(), name='dashboard'),
    path('aircraft/<uuid:pk>/', core_views.AircraftDetailView.as_view(), name='aircraft-detail'),
    path('aircraft/<uuid:pk>/squawks/history/', core_views.SquawkHistoryView.as_view(), name='squawk-history'),
    path('shared/<uuid:share_token>/', core_views.PublicAircraftView.as_view(), name='public-aircraft'),
    path('api/shared/<uuid:share_token>/', PublicAircraftSummaryAPI.as_view(), name='public-aircraft-api'),
    path('api/shared/<uuid:share_token>/logbook-entries/', PublicLogbookEntriesAPI.as_view(), name='public-logbook-entries'),
    path('tools/import-logbook/', core_views.LogbookImportView.as_view(), name='logbook-import'),
    path('tools/import-logbook/<uuid:job_id>/status/', core_views.LogbookImportView.as_view(), name='logbook-import-status'),
    path('api/aircraft/<uuid:pk>/export/', core_views.ExportView.as_view(), name='aircraft-export'),
    path('api/aircraft/import/', core_views.ImportView.as_view(), name='aircraft-import'),
    path('api/aircraft/import/<uuid:job_id>/', core_views.ImportJobStatusView.as_view(), name='aircraft-import-status'),
    path('register/<uuid:token>/', core_views.RegisterView.as_view(), name='register'),
    path('accounts/profile/', core_views.ProfileView.as_view(), name='profile'),
    path('api/user-search/', core_views.UserSearchView.as_view(), name='user-search'),
    path('manage/', RedirectView.as_view(url='/manage/invitations/'), name='manage'),
    path('manage/invitations/', core_views.ManageInvitationsView.as_view(), name='manage-invitations'),
    path('manage/invitations/<uuid:pk>/', core_views.ManageInvitationDetailView.as_view(), name='manage-invitation-detail'),
    path('manage/users/', core_views.ManageUsersView.as_view(), name='manage-users'),
    path('api/', include(router.urls)),
    path('admin/', admin.site.urls),
    path("accounts/logout/", core_views.custom_logout, name='logout'),  # Custom logout before django.contrib.auth.urls
    path("accounts/", include("django.contrib.auth.urls")),
    path('api-auth/', include('rest_framework.urls')),
    # Conditionally include OIDC URLs if OIDC is enabled
    *([path('oidc/', include('mozilla_django_oidc.urls'))] if getattr(settings, 'OIDC_ENABLED', False) else []),
]

# Auto-include page URLs from SAM plugins that declare a url_prefix.
for _app_config in _django_apps.get_app_configs():
    if getattr(_app_config, 'sam_plugin', False) and getattr(_app_config, 'url_prefix', None):
        try:
            urlpatterns.append(
                path(f'{_app_config.url_prefix}/', include(f'{_app_config.name}.urls'))
            )
        except Exception:
            pass  # Don't crash startup if a plugin's page URLs fail to load

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
