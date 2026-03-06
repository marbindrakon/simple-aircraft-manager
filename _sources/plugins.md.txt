# Plugin System

Simple Aircraft Manager supports out-of-tree plugins — standalone Django apps that extend the UI, API, and dashboard without modifying core source files.

## How Plugins Work

Plugins are ordinary Django `AppConfig` subclasses that inherit from `SAMPluginConfig` (in `core/plugins.py`). SAM discovers them at startup, adds them to `INSTALLED_APPS`, and wires up their extension-point declarations automatically.

A plugin can:

- Add navigation links and management views to the global navbar
- Add new tabs (primary or sub-tabs) to the aircraft detail page
- Register new API endpoints via the DRF router
- Contribute Alpine.js mixins to the aircraft detail page
- Add dashboard tiles (per-aircraft or global)
- Serve its own Django URL patterns

## Plugin Discovery

SAM finds plugins via two mechanisms, checked every time settings are loaded:

| Mechanism | Env var | Description |
|-----------|---------|-------------|
| Directory scan | `SAM_PLUGIN_DIR` | Scans this directory for packages (subdirs with `__init__.py`). Default: `/plugins`. |
| Explicit list | `SAM_PLUGINS` | Comma-separated Python module names to add directly to `INSTALLED_APPS`. |

Both mechanisms can be used simultaneously. Duplicate entries are ignored.

In a container environment (recommended), set `SAM_PLUGIN_PACKAGES` to install plugin packages from PyPI (or a private registry) at startup before migrations and `collectstatic` run:

```
SAM_PLUGIN_PACKAGES=my-sam-plugin==1.2.0,another-plugin>=0.5
```

See [configuration.md](configuration.md) for all plugin-related environment variables.

## Writing a Plugin

### 1. Create the Django app

```
my_plugin/
├── __init__.py
├── apps.py            # SAMPluginConfig subclass
├── models.py          # optional
├── urls.py            # page URL patterns (optional)
├── api_urls.py        # DRF router registrations (optional)
├── templates/
│   └── my_plugin/
│       └── includes/
│           └── detail_engine_monitor.html
└── static/
    └── js/
        └── my-plugin-mixin.js
```

### 2. Declare the AppConfig

```python
# my_plugin/apps.py
from core.plugins import SAMPluginConfig

class MyPluginConfig(SAMPluginConfig):
    name = 'my_plugin'
    verbose_name = 'My Plugin'
    default_auto_field = 'django.db.models.BigAutoField'

    # Extension points (all optional):
    nav_items = [
        {
            'label': 'Engine Monitor',
            'url': '/engine-monitor/',
            'icon': 'fas fa-tachometer-alt',
            # 'staff_only': True,  # hide from non-staff users
        },
    ]

    aircraft_tabs = [
        {
            'key': 'engine-monitor',          # unique tab key / activeTab value
            'label': 'Engine Monitor',
            'primary_group': 'engine-monitor', # same as key = standalone tab
            'template': 'my_plugin/includes/detail_engine_monitor.html',
            # 'visibility': 'featureFlightTracking',  # Alpine.js expression
        },
    ]

    aircraft_js_files = ['js/my-plugin-mixin.js']

    aircraft_features = [
        {
            # Prefix slugs with your plugin name to avoid collisions with
            # other plugins. Convention: <plugin_name>_<feature>.
            'name': 'engine_monitor_alerts',   # slug used in DB, API, and JS
            'label': 'Engine Monitor Alerts',  # shown in the Settings tab
            'description': 'EGT/CHT threshold alerts and notifications',
        },
    ]

    global_dashboard_tiles = [
        {'template': 'my_plugin/includes/dashboard_fleet_summary.html'},
    ]
```

Set `default_app_config = 'my_plugin.apps.MyPluginConfig'` in `my_plugin/__init__.py`, or use the `AppConfig` auto-discovery mechanism (Django 3.2+).

### 3. Extension points reference

#### `nav_items`

Adds links to the global navigation bar.

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `label` | str | Yes | Display text |
| `url` | str | Yes | Absolute URL path |
| `icon` | str | No | FontAwesome class (e.g. `fas fa-plane`) |
| `staff_only` | bool | No | Hide from non-staff users (default `False`) |

#### `management_views`

Adds items under the staff "Manage" dropdown in the navbar.

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `label` | str | Yes | Display text |
| `url` | str | Yes | Absolute URL path |

#### `aircraft_tabs`

Adds tabs to the aircraft detail page. Two modes:

- **Standalone tab** — set `primary_group` equal to `key`. The tab appears as a new top-level tab alongside built-in tabs.
- **Sub-tab** — set `primary_group` to an existing built-in group key (e.g. `'consumables'`, `'compliance'`, `'logbook'`, `'records'`). The tab appears as a sub-tab inside that group via the `{% plugin_sub_tab_buttons %}` / `{% plugin_sub_tab_panels %}` template tags.

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `key` | str | Yes | Unique identifier; used as the Alpine.js `activeTab` value |
| `label` | str | Yes | Tab display label |
| `primary_group` | str | Yes | `key` for standalone; existing group key for sub-tabs |
| `template` | str | Yes | Django template path for the tab content |
| `visibility` | str | No | Alpine.js expression for `x-show` (omit to always show) |

#### `aircraft_features`

Per-aircraft feature flags contributed by the plugin. Each entry is a dict with:

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `name` | str | Yes | Unique slug. Must be globally unique across builtins and all plugins. Used in the DB, API, and JS (`this.features['name']`). **Strongly recommended: prefix with your plugin name** (e.g. `engine_monitor_limits` not `limits`) — see note below. |
| `label` | str | Yes | Human-readable name shown in the Settings tab toggle list. |
| `description` | str | Yes | One-line description shown below the label in the Settings tab. |

> **Namespace your slugs.** Feature names share a single global namespace across all installed plugins and built-in features. A generic name like `limits` or `alerts` will collide silently with another plugin that chose the same name, causing one plugin to control the other's toggle. Always prefix with your plugin identifier: `engine_monitor_limits`, `engine_monitor_alerts`, etc. The convention is `<plugin_name>_<feature>` using the same snake_case name as your Django app.

Registered features behave identically to built-in features:

- All features default to **enabled**. Owners can toggle them on the aircraft Settings tab.
- Admins can globally disable a feature via the `DISABLED_FEATURES` environment variable.
- Use `feature_available('engine_monitor_alerts', aircraft)` in Python for server-side checks.
- Access the boolean state in Alpine.js via `this.features['engine_monitor_alerts']` (returns `undefined` — truthy — until features are loaded, so `!== false` is the safe guard).
- Plugin tab `visibility` expressions can reference feature state: `'features["engine_monitor_alerts"] !== false'`.

#### `aircraft_js_files`

List of static file paths (relative to `STATIC_ROOT`) loaded on the aircraft detail page **before** `aircraft-detail.js`. Use this to register Alpine.js mixins and tab mappings.

#### `aircraft_dashboard_tiles`

Per-aircraft tiles rendered on each aircraft card on the dashboard.

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `template` | str | Yes | Django template path |

#### `global_dashboard_tiles`

Sections rendered at the bottom of the fleet dashboard (not per-aircraft).

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `template` | str | Yes | Django template path |

#### `url_prefix`

If set, SAM includes the plugin's `urls.urlpatterns` at `/<url_prefix>/`.

#### `api_url_prefix`

If set, SAM registers `ROUTER_REGISTRATIONS` from `api_urls.py` in the DRF router. Alternatively, place `ROUTER_REGISTRATIONS` in `urls.py` (same format as `core/urls.py`).

## Frontend Integration (Alpine.js)

### Registering a mixin

Plugin JS files are loaded before `aircraft-detail.js`. Push mixin factory functions onto `window.SAMPluginMixins`:

```javascript
// my_plugin/static/js/my-plugin-mixin.js
window.SAMPluginMixins = window.SAMPluginMixins || [];
window.SAMPluginMixins.push(function myPluginMixin() {
    return {
        // reactive data
        engineData: [],

        // lifecycle — called when the detail page initialises
        async initMyPlugin() {
            const { ok, data } = await apiRequest(`/api/aircraft/${this.aircraftId}/engine-data/`);
            if (ok) this.engineData = data;
        },

        // getters, methods, etc.
        get hasEngineData() {
            return this.engineData.length > 0;
        },
    };
});
```

The composer (`aircraft-detail.js`) merges all plugin mixins via `mergeMixins()` before the built-in mixins. Plugin state, getters, and methods are available on `this` inside any other mixin.

### Registering sub-tab mappings

For sub-tabs inside an existing primary group, register the mapping so the tab navigation can resolve `activeTab` back to the correct primary group:

```javascript
window.SAMPluginTabMappings = window.SAMPluginTabMappings || {};
window.SAMPluginTabMappings['my-sub-tab-key'] = 'consumables';
```

### Accessing core state

All core reactive properties are available on `this` inside plugin mixins:

| Property | Type | Description |
|----------|------|-------------|
| `aircraftId` | str | Aircraft UUID |
| `activeTab` | str | Currently active tab key |
| `userRole` | str | `'admin'` / `'owner'` / `'pilot'` / `null` |
| `isOwner` | bool | User is owner or admin |
| `isPilot` | bool | User is pilot or above |
| `canWrite` | bool | User can write (owner-level actions) |
| `isPublicView` | bool | Viewed via share link (no auth) |
| `features` | object | Dict of `{slug: bool}` for all registered features (builtin + plugin). Safe guard: `features['my_slug'] !== false` (undefined = enabled). |
| `featureCatalog` | array | Ordered list of `{name, label, description}` for all registered features. Populated from the API; iterate this to render feature UI. |
| `featureFlightTracking` | bool | Flight Tracking feature enabled |
| `featureOilConsumption` | bool | Oil Consumption feature enabled |
| `featureFuelConsumption` | bool | Fuel Consumption feature enabled |
| `featureOilAnalysis` | bool | Oil Analysis feature enabled |
| `featureSharing` | bool | Public Sharing feature enabled |
| `featureAirworthinessEnforcement` | bool | Airworthiness Enforcement enabled |

For **plugin-defined features**, read the boolean from `this.features`:

```javascript
// In a plugin mixin or x-show expression:
get engineMonitorEnabled() {
    return this.features['engine_monitor_alerts'] !== false;
},
```

Or in a template `aircraft_tabs` entry:

```python
aircraft_tabs = [
    {
        'key': 'engine-monitor',
        'label': 'Engine Monitor',
        'primary_group': 'engine-monitor',
        'template': 'my_plugin/includes/detail_engine_monitor.html',
        'visibility': 'features["engine_monitor_alerts"] !== false',
    },
]
```

Use these to conditionally show/hide content via `x-show` in your templates.

## Template Integration

### Sub-tab buttons and panels

Built-in primary groups that support plugin sub-tabs render them via Sphinx template tags. Load the tag library and place the tags inside your primary group's tab button row and panel area:

```html
{% load sam_plugins %}

<!-- In the tab button row -->
{% plugin_sub_tab_buttons "consumables" %}

<!-- In the tab panel area -->
{% plugin_sub_tab_panels "consumables" %}
```

These tags are already wired into `detail_consumables.html`, `detail_compliance.html`, `detail_logbook.html`, and `detail_records.html`. For a new standalone tab, include content directly in your tab template.

### Accessing the plugin registry in templates

The `plugin_registry` context variable is available in all templates (injected by `core/context_processors.py`):

```html
{% for item in plugin_registry.nav_items %}
    <a href="{{ item.url }}">{{ item.label }}</a>
{% endfor %}
```

## Adding API Endpoints

Define `ROUTER_REGISTRATIONS` in `api_urls.py` (or `urls.py`):

```python
# my_plugin/api_urls.py
from rest_framework.routers import DefaultRouter
from .views import EngineDataViewSet

ROUTER_REGISTRATIONS = [
    ('engine-data', EngineDataViewSet, 'engine-data'),
]
```

This registers the viewset at `/api/engine-data/`. Use `AircraftScopedMixin` and `EventLoggingMixin` from `core/mixins.py` for consistent RBAC and event logging:

```python
from core.mixins import AircraftScopedMixin, EventLoggingMixin
from rest_framework import viewsets
from .models import EngineReading
from .serializers import EngineReadingSerializer

class EngineDataViewSet(AircraftScopedMixin, EventLoggingMixin, viewsets.ModelViewSet):
    serializer_class = EngineReadingSerializer
    aircraft_fk_path = 'aircraft'
    event_category = 'engine'

    def get_queryset(self):
        return EngineReading.objects.filter(
            aircraft__in=self.get_accessible_aircraft()
        )
```

## Packaging as a Python Package

A plugin can be packaged as a standard Python distribution (`pyproject.toml` / `setup.cfg`). Set the `default_app_config` (or use entry-point auto-discovery). Distribute via PyPI or a private index.

Install at container startup via `SAM_PLUGIN_PACKAGES`:

```
SAM_PLUGIN_PACKAGES=my-sam-plugin==1.2.0
SAM_PLUGINS=my_plugin          # module name inside the package
```

The entrypoint script pip-installs the packages, runs `collectstatic` to pick up static assets, and then starts the server.

## Plugin Checklist

- [ ] Subclass `SAMPluginConfig` (not `AppConfig`)
- [ ] Set `name`, `verbose_name`, `default_auto_field`
- [ ] Declare extension points as class attributes (only what you need)
- [ ] `aircraft_features` entries have unique slugs and include `name`, `label`, and `description`
- [ ] JS mixin pushed to `window.SAMPluginMixins`; sub-tab keys registered in `window.SAMPluginTabMappings`
- [ ] Static files in `<app>/static/`; template files in `<app>/templates/<app>/`
- [ ] API viewsets use `AircraftScopedMixin` + `EventLoggingMixin`
- [ ] Models use UUID primary keys
- [ ] Migrations included in the package
- [ ] `collectstatic` runs at startup (handled by entrypoint when `SAM_PLUGIN_PACKAGES` or `SAM_PLUGIN_DIR` is set)
