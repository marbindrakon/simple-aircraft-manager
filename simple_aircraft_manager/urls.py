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
from django.contrib import admin
from django.conf.urls.static import static
from django.conf import settings
from django.urls import path, include
from django.views.generic import RedirectView

from rest_framework import routers

from core import views as core_views
from health import views as health_views

router = routers.DefaultRouter()
router.register(r'aircraft', core_views.AircraftViewSet)
router.register(r'aircraft-notes', core_views.AircraftNoteViewSet)
router.register(r'aircraft-events', core_views.AircraftEventViewSet)
router.register(r'component-types', health_views.ComponentTypeViewSet)
router.register(r'components', health_views.ComponentViewSet)
router.register(r'document-collections', health_views.DocumentCollectionViewSet)
router.register(r'documents', health_views.DocumentViewSet)
router.register(r'document-images', health_views.DocumentImageViewSet)
router.register(r'logbook-entries', health_views.LogbookEntryViewSet)
router.register(r'squawks', health_views.SquawkViewSet)
router.register(r'inspection-types', health_views.InspectionTypeViewSet)
router.register(r'ads', health_views.ADViewSet)
router.register(r'major-records', health_views.MajorRepairAlterationViewSet)
router.register(r'inspections', health_views.InspectionRecordViewSet)
router.register(r'ad-compliances', health_views.ADComplianceViewSet)
router.register(r'consumable-records', health_views.ConsumableRecordViewSet)


urlpatterns = [
    path('healthz/', core_views.healthz, name='healthz'),
    path('', RedirectView.as_view(url='/dashboard/', permanent=False), name='home'),
    path('dashboard/', core_views.DashboardView.as_view(), name='dashboard'),
    path('aircraft/<uuid:pk>/', core_views.AircraftDetailView.as_view(), name='aircraft-detail'),
    path('aircraft/<uuid:pk>/squawks/history/', core_views.SquawkHistoryView.as_view(), name='squawk-history'),
    path('shared/<uuid:share_token>/', core_views.PublicAircraftView.as_view(), name='public-aircraft'),
    path('api/shared/<uuid:share_token>/', core_views.PublicAircraftSummaryAPI.as_view(), name='public-aircraft-api'),
    path('api/shared/<uuid:share_token>/logbook-entries/', core_views.PublicLogbookEntriesAPI.as_view(), name='public-logbook-entries'),
    path('tools/import-logbook/', core_views.LogbookImportView.as_view(), name='logbook-import'),
    path('tools/import-logbook/<uuid:job_id>/status/', core_views.LogbookImportView.as_view(), name='logbook-import-status'),
    path('api/aircraft/<uuid:pk>/export/', core_views.ExportView.as_view(), name='aircraft-export'),
    path('api/aircraft/import/', core_views.ImportView.as_view(), name='aircraft-import'),
    path('api/aircraft/import/<uuid:job_id>/', core_views.ImportJobStatusView.as_view(), name='aircraft-import-status'),
    path('api/user-search/', core_views.UserSearchView.as_view(), name='user-search'),
    path('api/', include(router.urls)),
    path('admin/', admin.site.urls),
    path("accounts/logout/", core_views.custom_logout, name='logout'),  # Custom logout before django.contrib.auth.urls
    path("accounts/", include("django.contrib.auth.urls")),
    path('api-auth/', include('rest_framework.urls')),
    # Conditionally include OIDC URLs if OIDC is enabled
    *([path('oidc/', include('mozilla_django_oidc.urls'))] if getattr(settings, 'OIDC_ENABLED', False) else []),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
