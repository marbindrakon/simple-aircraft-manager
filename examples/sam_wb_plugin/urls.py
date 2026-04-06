"""Page URL patterns for the Weight & Balance plugin.

Included by SAM's main urls.py at /wb/ when url_prefix = 'wb' is set
in WBPluginConfig.
"""

from django.urls import path

from .views import WBConfigListView

urlpatterns = [
    path('', WBConfigListView.as_view(), name='wb-config-list'),
]
