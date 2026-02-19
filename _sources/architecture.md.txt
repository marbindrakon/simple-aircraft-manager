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
│   ├── models.py                # Aircraft, AircraftNote, AircraftEvent, roles, share tokens
│   ├── views.py                 # API ViewSets + template views + public sharing
│   ├── serializers.py           # DRF serializers
│   ├── permissions.py           # RBAC permission classes
│   ├── mixins.py                # AircraftScopedMixin, EventLoggingMixin
│   ├── events.py                # Event logging (log_event)
│   ├── oidc.py                  # OIDC backend + logout URL builder
│   ├── context_processors.py    # Template context (OIDC_ENABLED)
│   ├── templates/
│   │   ├── base.html            # Base template with PatternFly + Alpine.js
│   │   ├── dashboard.html       # Fleet dashboard
│   │   ├── aircraft_detail.html # Tabbed aircraft detail page
│   │   └── includes/            # Reusable template partials
│   └── static/
│       ├── css/app.css          # Custom styles
│       └── js/                  # Alpine.js components (see below)
├── health/                      # Maintenance & compliance
│   ├── models.py                # Component, Squawk, Logbook, AD, Inspection, etc.
│   ├── views.py                 # API ViewSets
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

Composer: `aircraft-detail.js`. **Never use `{...spread}` to merge mixins** — it eagerly evaluates `get` properties. `mergeMixins()` preserves getter descriptors via `Object.getOwnPropertyDescriptors()`.

Shared utilities in `utils.js` (loaded globally via `base.html`): `getCookie`, `mergeMixins`, `apiRequest`, `showNotification`, `formatDate`, `formatHours`, `getAirworthinessClass/Text/Tooltip`, `getSquawkPriorityClass`, `formatApiError`.

## Airworthiness Calculation

`calculate_airworthiness(aircraft)` in `health/services.py` checks in order:
1. AD compliance
2. Grounding squawks (priority 0)
3. Inspection recurrency
4. Component replacement intervals

Thresholds: overdue → RED; within 10 hours / 30 days → ORANGE.

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
