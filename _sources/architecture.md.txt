# Architecture

## Technology Stack

### Backend
- **Django 5.2** — Web framework
- **Django REST Framework** — RESTful API
- **django-filter** — Advanced queryset filtering
- **mozilla-django-oidc** — OpenID Connect authentication
- **Pillow** — Image handling for documents and media
- **Gunicorn** — Production WSGI server
- **SQLite** — Development database
- **PostgreSQL** — Production database
- **Python 3.11+**

### Frontend
- **PatternFly 5** — Enterprise UI framework (no build tools; loaded from CDN)
- **Alpine.js 3** — Lightweight reactive framework (~3KB)
- **Chart.js 4** — Oil/fuel consumption charts
- **Font Awesome** — Icons

No build pipeline. All JS is vanilla Alpine.js loaded as static files or from CDN.

### Deployment
- **Red Hat UBI 9** — Container base image
- **nginx** — Static/media file serving and TLS termination (sidecar)
- **OpenShift / Kubernetes** — Container platform

## Project Structure

```
simple-aircraft-manager/
├── simple_aircraft_manager/     # Project configuration
│   ├── settings.py              # Development settings (SQLite, DEBUG=True)
│   ├── settings_prod.py         # Production settings (requires env vars)
│   ├── urls.py                  # URL routing
│   └── wsgi.py
├── core/                        # Core aircraft management
│   ├── models.py                # Aircraft, AircraftNote, AircraftEvent, AircraftFeature, roles, share tokens
│   ├── features.py              # feature_available() helper — per-aircraft feature flag resolution
│   ├── plugins.py               # SAMPluginConfig base class + PluginRegistry singleton
│   ├── views/                   # Views package (split from core/views.py)
│   │   ├── __init__.py          # Re-exports all public names for backwards compatibility
│   │   ├── aircraft.py          # AircraftViewSet (uses HealthAircraftActionsMixin)
│   │   ├── auth_views.py        # custom_logout, RegisterView, ProfileView
│   │   ├── public_views.py      # PublicAircraftView (token → template render)
│   │   ├── import_export_views.py # ExportView, ImportView, ImportJobStatusView
│   │   ├── template_views.py    # DashboardView, AircraftDetailView, SquawkHistoryView
│   │   ├── logbook_import_view.py # LogbookImportView
│   │   ├── notes_events.py      # AircraftNoteViewSet, AircraftEventViewSet, healthz
│   │   ├── user_views.py        # UserSearchView
│   │   └── invitations.py       # InvitationCodeViewSet, manage views
│   ├── action_registry.py       # Permission routing registry (plugin pattern)
│   ├── sharing.py               # validate_share_token() helper
│   ├── urls.py                  # ROUTER_REGISTRATIONS list for core routes
│   ├── serializers.py           # DRF serializers
│   ├── permissions.py           # RBAC permission classes
│   ├── mixins.py                # AircraftScopedMixin, EventLoggingMixin
│   ├── events.py                # Event logging (log_event)
│   ├── export.py                # Aircraft export — builds manifest + streams .sam.zip
│   ├── import_export.py         # Aircraft import — validation, ID remapping, background runner
│   ├── oidc.py                  # OIDC backend + logout URL builder
│   ├── context_processors.py    # Template context (OIDC_ENABLED, plugin_registry, etc.)
│   ├── templatetags/
│   │   └── sam_plugins.py       # {% plugin_sub_tab_buttons %} / {% plugin_sub_tab_panels %}
│   ├── management/commands/
│   │   ├── export_aircraft.py   # CLI export command
│   │   └── import_aircraft.py   # CLI import command
│   ├── templates/
│   │   ├── base.html            # Base template with PatternFly + Alpine.js
│   │   ├── dashboard.html       # Fleet dashboard
│   │   ├── aircraft_detail.html # Parent aircraft detail template (~262 lines)
│   │   └── includes/            # Tab section includes (detail_overview.html, detail_components.html, etc.)
│   └── static/
│       ├── css/app.css          # Custom styles
│       └── js/                  # Alpine.js components (see below)
├── health/                      # Maintenance & compliance
│   ├── models.py                # Component, Squawk, Logbook, AD, Inspection, etc.
│   ├── views.py                 # API ViewSets
│   ├── aircraft_actions.py      # HealthAircraftActionsMixin — all @action methods for AircraftViewSet
│   ├── serializer_mixins.py     # AirworthinessMixin
│   ├── views_public.py          # PublicAircraftSummaryAPI, PublicLogbookEntriesAPI
│   ├── urls.py                  # ROUTER_REGISTRATIONS list for health routes
│   ├── serializers.py           # DRF serializers (includes upload validation)
│   ├── services.py              # Airworthiness calculation logic
│   └── logbook_import.py        # AI-assisted logbook transcription
├── examples/openshift/          # OpenShift deployment manifests
├── Containerfile                # Container image definition
├── docker-entrypoint.sh         # Container startup script
├── requirements.txt             # Development dependencies
└── requirements-prod.txt        # Production dependencies
```

## Frontend Architecture (Alpine.js Mixin Pattern)

The aircraft detail page is composed from feature mixins merged by `mergeMixins()` in `utils.js`:

| File | Function | Feature |
|------|----------|---------|
| `aircraft-detail-components.js` | `componentsMixin()` | Component CRUD, tree sorting, status |
| `aircraft-detail-squawks.js` | `squawksMixin()` | Squawk CRUD, priority helpers |
| `aircraft-detail-notes.js` | `notesMixin()` | Note CRUD |
| `aircraft-detail-oil.js` | `oilMixin()` | Oil record CRUD, consumption chart |
| `aircraft-detail-fuel.js` | `fuelMixin()` | Fuel record CRUD, burn rate chart |
| `aircraft-detail-logbook.js` | `logbookMixin()` | Logbook CRUD, file uploads, AI import |
| `aircraft-detail-ads.js` | `adsMixin()` | AD CRUD, compliance records, history |
| `aircraft-detail-inspections.js` | `inspectionsMixin()` | Inspection CRUD, history |
| `aircraft-detail-documents.js` | `documentsMixin()` | Document/collection CRUD, viewer |
| `aircraft-detail-major-records.js` | `majorRecordsMixin()` | Major repair/alteration CRUD |
| `aircraft-detail-events.js` | `eventsMixin()` | Recent activity card, history modal |
| `aircraft-detail-roles.js` | `rolesMixin()` | Role management, public sharing toggle |
| `aircraft-detail-features.js` | `featuresMixin()` | Per-aircraft feature flag toggles (Settings tab) |

Composer: `aircraft-detail.js`. **Never use `{...spread}` to merge mixins** — it eagerly evaluates `get` properties. `mergeMixins()` preserves getter descriptors via `Object.getOwnPropertyDescriptors()`.

Plugin mixins are loaded before built-in mixins. Plugin JS files push mixin factory functions onto `window.SAMPluginMixins`; the composer merges them first so plugin state is available on `this` inside built-in mixins.

Shared utilities in `utils.js` (loaded globally via `base.html`): `getCookie`, `mergeMixins`, `apiRequest`, `showNotification`, `formatDate`, `formatHours`, `getAirworthinessClass/Text/Tooltip`, `getSquawkPriorityClass`, `formatApiError`.

## Plugin System

SAM supports out-of-tree plugins — standalone Django apps that extend UI, API, and dashboard without patching core code. Plugins subclass `SAMPluginConfig` from `core/plugins.py`, which registers them with the `PluginRegistry` singleton during `AppConfig.ready()`.

Discovery: `SAM_PLUGIN_DIR` (directory scan) and `SAM_PLUGINS` (explicit module list) env vars. In containers, `SAM_PLUGIN_PACKAGES` installs packages from PyPI before startup. See [plugins.md](plugins.md) for the full developer guide.

## Per-Aircraft Feature Flags

`AircraftFeature` rows in `core/models.py` store per-aircraft enable/disable state for each named feature. The `feature_available(feature_name, aircraft)` helper in `core/features.py` resolves flags in priority order: global `DISABLED_FEATURES` setting → per-aircraft row → default (enabled). See [feature-flags.md](feature-flags.md) for details.

## Airworthiness Calculation

`calculate_airworthiness(aircraft)` in `health/services.py` checks in order:
1. AD compliance
2. Grounding squawks (priority 0)
3. Inspection recurrency
4. Component replacement intervals

Thresholds: overdue → RED; within 10 hours / 30 days → ORANGE.

## Aircraft Import / Export

### Archive format (`.sam.zip`)

A `.sam.zip` file is a standard ZIP archive containing:

| Path | Description |
|------|-------------|
| `manifest.json` | All aircraft data (JSON, ≤ 50 MB) |
| `attachments/<original_storage_path>` | Attached files (pictures, document images, squawk attachments) |

### Manifest schema

`manifest.json` is a JSON object. The `schema_version` field controls compatibility.

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | int | Archive schema version (currently `1`) |
| `exported_at` | ISO 8601 string | Export timestamp |
| `source_instance` | string | `ALLOWED_HOSTS[0]` of the exporting instance |
| `aircraft` | object | Aircraft fields |
| `component_types` | array | Component type definitions used by this aircraft |
| `components` | array | All components (parent-child relationships preserved) |
| `document_collections` | array | Document collections |
| `documents` | array | Documents |
| `document_images` | array | Document images with `attachments/…` paths |
| `squawks` | array | Squawks with `attachments/…` paths |
| `inspection_types` | array | Inspection type definitions |
| `inspection_records` | array | Inspection compliance records |
| `ads` | array | Airworthiness Directives |
| `ad_compliances` | array | AD compliance records |
| `consumable_records` | array | Oil and fuel records |
| `major_records` | array | Major repair/alteration records |
| `notes` | array | Aircraft notes |

All UUIDs are serialized as strings. Decimal values (hours, quantities) are serialized as strings to avoid float precision loss. Missing files are flagged with `"_missing": true` on the containing object — they are omitted from the archive but do not block export.

### Schema versioning

`CURRENT_SCHEMA_VERSION = 1` is defined in `core/import_export.py`. The importer rejects any archive whose `schema_version` is greater than `CURRENT_SCHEMA_VERSION`. Older versions (lower numbers) are accepted.

When a new schema version is needed (e.g., new required fields, renamed keys):

1. Bump `SCHEMA_VERSION` in `core/export.py` and `CURRENT_SCHEMA_VERSION` in `core/import_export.py` to the same value.
2. Add migration logic in `run_aircraft_import_job` for archives with older `schema_version` values.
3. Update `KNOWN_MANIFEST_KEYS` if top-level keys changed.

### Import pipeline

1. **`validate_archive_quick()`** (synchronous, in-view) — ZIP safety checks (zip bomb, symlinks, path traversal), manifest parsing, schema version check, tail-number conflict detection.
2. **`run_aircraft_import_job()`** (background thread) — full validation, record creation inside a `transaction.atomic()` block with rollback on error, file extraction, and job status updates.
3. **ID remapping** — all UUIDs from the manifest are re-keyed to fresh UUIDs on the target instance. Cross-references (e.g., `component_id` on a squawk) are resolved via in-memory maps built during import.

### Security checks

- Zip bomb: total uncompressed size vs. `IMPORT_MAX_ARCHIVE_SIZE`; compression ratio ≤ 100:1
- Symlink entries rejected
- Path traversal: all entry names are NFC-normalized; `..` components and absolute paths rejected
- Magic-byte validation for all attached files (jpg, png, gif, webp, bmp, tiff, pdf)
- Per-entity record count limits (configurable via `_DEFAULT_LIMITS` in `core/import_export.py`)

## Content Security Policy

All JS must be external files in `core/static/js/` — inline `<script>` blocks are blocked by CSP. CDN allowlist: scripts from `cdn.jsdelivr.net`, styles from `unpkg.com`. Adding a new CDN requires updating `nginx-config.yaml` in the deployment manifests.

## Contributing

1. Follow the existing Django app structure (`core/` for aircraft-level models, `health/` for maintenance records)
2. Use UUID primary keys for new models
3. Add `AircraftScopedMixin` and `EventLoggingMixin` to new ViewSets (see `CLAUDE.md`)
4. Run migrations after model changes: `python manage.py makemigrations && python manage.py migrate`
5. Verify production settings: `DJANGO_SECRET_KEY=test DJANGO_ALLOWED_HOSTS=localhost python manage.py check --settings=simple_aircraft_manager.settings_prod`
6. Register new models in `admin.py`
7. For new JS features, create `aircraft-detail-<feature>.js` and add it to the composer and template
8. For new per-aircraft feature flags, add the key to `KNOWN_FEATURES` in `core/models.py`, add a getter in `aircraft-detail.js`, and document it in `docs/feature-flags.md` and `docs/user-guide/sharing-and-access.rst`
9. For new extension points in the plugin system, add class attributes to `SAMPluginConfig`, aggregation properties to `PluginRegistry`, and document them in `docs/plugins.md`
