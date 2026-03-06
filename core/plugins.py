"""SAM Plugin System — base class and registry singleton.

Plugins are out-of-tree Django apps that subclass SAMPluginConfig.
They are discovered via the SAM_PLUGIN_DIR / SAM_PLUGINS env vars and
auto-added to INSTALLED_APPS by the settings module.

Example plugin AppConfig::

    # my_plugin/apps.py
    from core.plugins import SAMPluginConfig

    class MyPluginConfig(SAMPluginConfig):
        name = 'my_plugin'
        verbose_name = 'My Plugin'

        # Declare extension points:
        nav_items = [
            {'label': 'Engine Monitor', 'url': '/engine-monitor/', 'icon': 'fas fa-tachometer-alt'},
        ]
        aircraft_tabs = [
            {
                'key': 'engine-monitor',
                'label': 'Engine Monitor',
                'primary_group': 'engine-monitor',
                'template': 'my_plugin/includes/detail_engine_monitor.html',
            },
        ]
        aircraft_js_files = ['js/my-plugin-mixin.js']

Extension points
----------------
nav_items
    List of dicts added to the global navbar.  Keys:
    - ``label`` (str, required)
    - ``url`` (str, required) — absolute path
    - ``icon`` (str) — FontAwesome class, e.g. ``'fas fa-plane'``
    - ``staff_only`` (bool, default False)

management_views
    List of dicts added under the staff "Manage" navbar link.  Keys:
    - ``label`` (str, required)
    - ``url`` (str, required)

aircraft_tabs
    List of dicts for new primary tabs on the aircraft detail page.  Keys:
    - ``key`` (str, required) — unique tab identifier, used as ``activeTab``
    - ``label`` (str, required) — display label
    - ``primary_group`` (str, required) — for standalone tabs set equal to
      ``key``; for plugin sub-tabs within an *existing* primary group set to
      that group's key (e.g. ``'consumables'``).
    - ``template`` (str, required) — Django template path for the tab content
    - ``visibility`` (str) — optional Alpine.js expression; if omitted the tab
      is always shown (equivalent to ``x-show="true"``)

aircraft_js_files
    List of static file paths (relative to STATIC_ROOT) for JS files loaded
    on the aircraft detail page *before* ``aircraft-detail.js``.  Plugin JS
    files should push their mixin factory onto ``window.SAMPluginMixins``::

        window.SAMPluginMixins = window.SAMPluginMixins || [];
        window.SAMPluginMixins.push(function myPluginMixin() {
            return { ... };
        });

    To register tab mappings for sub-tabs::

        window.SAMPluginTabMappings = window.SAMPluginTabMappings || {};
        window.SAMPluginTabMappings['my-sub-tab'] = 'my-primary-group';

aircraft_dashboard_tiles
    List of dicts for per-aircraft dashboard card tiles.  Keys:
    - ``template`` (str, required) — Django template path

global_dashboard_tiles
    List of dicts for global sections on the dashboard page.  Keys:
    - ``template`` (str, required) — Django template path

URL extension
-------------
If the plugin has a ``url_prefix`` class attribute the main ``urls.py``
includes ``<app>.urls.urlpatterns`` at ``/<url_prefix>/``.

If the plugin has an ``api_url_prefix`` class attribute the main ``urls.py``
registers ``<app>.api_urls.ROUTER_REGISTRATIONS`` in the DRF router.
Alternatively, plugins may provide ``ROUTER_REGISTRATIONS`` in their own
``urls.py`` (following the same pattern as ``core/urls.py`` and
``health/urls.py``); the main router will pick them up automatically.
"""

from django.apps import AppConfig


class SAMPluginConfig(AppConfig):
    """Base AppConfig for SAM plugins.

    Subclass this in your plugin's ``apps.py`` instead of
    ``django.apps.AppConfig``.  See module docstring for details.
    """

    # Sentinel — checked by urls.py/context processors to identify SAM plugins
    # without importing this class (avoids circular import risk at URL-import time).
    sam_plugin = True

    # --- URL extension ---
    url_prefix: str | None = None
    api_url_prefix: str | None = None

    # --- Navigation ---
    nav_items: list = []
    management_views: list = []

    # --- Aircraft detail page ---
    aircraft_tabs: list = []
    aircraft_js_files: list = []

    # --- Dashboard ---
    aircraft_dashboard_tiles: list = []
    global_dashboard_tiles: list = []

    def ready(self):
        # Register with the singleton registry so templates / URL conf can
        # iterate all active plugins.
        registry.register(self)


class PluginRegistry:
    """Singleton that aggregates all active SAM plugin configs.

    Populated during Django startup (``AppConfig.ready()``).
    Accessed by templates via the ``plugin_registry`` context variable.
    """

    def __init__(self):
        self._plugins: list[SAMPluginConfig] = []

    def register(self, config: SAMPluginConfig) -> None:
        self._plugins.append(config)

    @property
    def plugins(self) -> list:
        return list(self._plugins)

    # --- Aggregated extension-point accessors ---

    @property
    def nav_items(self) -> list:
        items = []
        for p in self._plugins:
            items.extend(p.nav_items)
        return items

    @property
    def management_views(self) -> list:
        items = []
        for p in self._plugins:
            items.extend(p.management_views)
        return items

    @property
    def aircraft_tabs(self) -> list:
        tabs = []
        for p in self._plugins:
            tabs.extend(p.aircraft_tabs)
        return tabs

    @property
    def standalone_aircraft_tabs(self) -> list:
        """Tabs that are their own primary group (not sub-tabs of an existing group)."""
        return [
            t for t in self.aircraft_tabs
            if t.get('primary_group') == t.get('key')
        ]

    def sub_tabs_for(self, primary_group: str) -> list:
        """Return plugin sub-tabs registered under an existing primary group."""
        return [
            t for t in self.aircraft_tabs
            if t.get('primary_group') == primary_group and t.get('key') != primary_group
        ]

    @property
    def aircraft_js_files(self) -> list:
        files = []
        for p in self._plugins:
            files.extend(p.aircraft_js_files)
        return files

    @property
    def aircraft_dashboard_tiles(self) -> list:
        tiles = []
        for p in self._plugins:
            tiles.extend(p.aircraft_dashboard_tiles)
        return tiles

    @property
    def global_dashboard_tiles(self) -> list:
        tiles = []
        for p in self._plugins:
            tiles.extend(p.global_dashboard_tiles)
        return tiles


# Module-level singleton — imported by AppConfig.ready(), templates, and urls.py
registry = PluginRegistry()
