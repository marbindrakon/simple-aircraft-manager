"""SAM Weight & Balance Plugin — example plugin for Simple Aircraft Manager.

Demonstrates all major plugin extension points:
  - nav_items          → "Weight & Balance" link in the global navbar
  - management_views   → link in the staff "Manage" dropdown
  - aircraft_tabs      → standalone "W&B" tab on the aircraft detail page
  - aircraft_js_files  → Alpine.js mixin (sam-wb-mixin.js)
  - aircraft_features  → sam_wb_calculator per-aircraft feature flag
  - global_dashboard_tiles → fleet-level W&B configuration summary card
  - url_prefix         → management page at /wb/
  - api_url_prefix     → DRF viewsets registered via api_urls.py
"""

from core.plugins import SAMPluginConfig


class WBPluginConfig(SAMPluginConfig):
    name = 'sam_wb_plugin'
    verbose_name = 'Weight & Balance'
    default_auto_field = 'django.db.models.BigAutoField'
    # Django 5 auto-discovery: when multiple AppConfig subclasses are present
    # in the module namespace (e.g. because SAMPluginConfig is imported here),
    # set default = True so Django picks this class unambiguously.
    default = True

    # -----------------------------------------------------------------------
    # URL extension
    # -----------------------------------------------------------------------

    # Page views served at /wb/ (urlpatterns defined in urls.py)
    url_prefix = 'wb'

    # DRF viewsets registered in the main router (ROUTER_REGISTRATIONS in api_urls.py)
    api_url_prefix = 'wb'

    # -----------------------------------------------------------------------
    # Navigation
    # -----------------------------------------------------------------------

    nav_items = [
        {
            'label': 'Weight & Balance',
            'url': '/wb/',
            'icon': 'fas fa-balance-scale',
        },
    ]

    management_views = [
        {
            'label': 'W&B Configurations',
            'url': '/wb/',
        },
    ]

    # -----------------------------------------------------------------------
    # Aircraft detail page
    # -----------------------------------------------------------------------

    aircraft_tabs = [
        {
            # Standalone tab (primary_group == key) — appears alongside the
            # built-in Overview / Squawks / Components / … tabs.
            'key': 'wb-calculator',
            'label': 'W&B',
            'primary_group': 'wb-calculator',
            'template': 'sam_wb_plugin/includes/detail_wb.html',
            # Hide the tab when the owner has disabled the feature for this aircraft.
            'visibility': 'features["sam_wb_calculator"] !== false',
        },
    ]

    aircraft_js_files = ['js/sam-wb-mixin.js']

    # -----------------------------------------------------------------------
    # Feature flags
    # -----------------------------------------------------------------------

    aircraft_features = [
        {
            # Slug must be globally unique — prefix with the plugin name.
            'name': 'sam_wb_calculator',
            'label': 'Weight & Balance Calculator',
            'description': 'CG envelope calculator and saved loading scenario tracker',
        },
    ]

    # -----------------------------------------------------------------------
    # Dashboard tiles
    # -----------------------------------------------------------------------

    # Fleet-level summary rendered at the bottom of the dashboard.
    global_dashboard_tiles = [
        {'template': 'sam_wb_plugin/includes/dashboard_global_tile.html'},
    ]

    # NOTE: aircraft_dashboard_tiles are declared by the plugin API but
    # require per-aircraft tile rendering to be wired into dashboard.html
    # inside the Alpine x-for loop.  This plugin omits them to avoid
    # confusion — use global_dashboard_tiles for fleet-wide summaries instead.
