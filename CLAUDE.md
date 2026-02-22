# Claude Code Context

Simple Aircraft Manager — Django + DRF app for tracking aircraft maintenance, hours, and regulatory compliance. Frontend: PatternFly 5 + Alpine.js 3 + Chart.js 4 (no build tools).

## Domain Concepts

### Component Hours Fields

| Field | Purpose | Reset on service? |
|-------|---------|-------------------|
| `hours_in_service` | Total cumulative hours since installation | No — never resets on service |
| `hours_since_overhaul` | Hours since last overhaul or last service | Yes — resets on service for `replacement_critical` |

For service resets (`POST /api/components/{id}/reset_service/`):
- Always resets `hours_since_overhaul` → 0 and `overhaul_date` → today
- Optional body param `reset_in_service: true` also resets `hours_in_service` → 0 and `date_in_service` → today
- Use `reset_in_service=true` when the component is physically replaced (e.g. oil change); omit/false when serviced in place

### Component Critical Flags

- `replacement_critical` — periodic replacement; tracked via `replacement_hours` + `hours_since_overhaul` + `overhaul_date`
- `tbo_critical` — TBO limit (engines, props); tracked via `tbo_hours` + `hours_since_overhaul`
- `inspection_critical` — requires periodic inspections

### Squawk Priorities

```python
(0, "Ground Aircraft")          # RED — grounds the aircraft
(1, "Fix Soon")                 # ORANGE
(2, "Fix at Next Inspection")   # BLUE
(3, "Fix Eventually")           # GREY
```

### LogbookEntry

Documents **maintenance** (inspections, parts replaced, mechanic signoffs) — not per-flight records.

## Architecture Patterns

### Frontend: Alpine.js Mixin Pattern

Aircraft detail page is composed from feature mixins merged by `mergeMixins()` (`utils.js`):

| Mixin file | Function | Feature |
|-----------|----------|---------|
| `aircraft-detail-components.js` | `componentsMixin()` | Component CRUD, tree sorting, status, service reset modal |
| `aircraft-detail-squawks.js` | `squawksMixin()` | Squawk CRUD, priority helpers |
| `aircraft-detail-notes.js` | `notesMixin()` | Note CRUD |
| `aircraft-detail-consumables.js` | `makeConsumableMixin(cfg)` | Shared factory for oil/fuel mixins |
| `aircraft-detail-oil.js` | `oilMixin()` | Oil record CRUD, consumption chart |
| `aircraft-detail-fuel.js` | `fuelMixin()` | Fuel record CRUD, burn rate chart |
| `aircraft-detail-logbook.js` | `logbookMixin()` | Logbook CRUD, file uploads |
| `aircraft-detail-ads.js` | `adsMixin()` | AD CRUD, compliance records, history |
| `aircraft-detail-inspections.js` | `inspectionsMixin()` | Inspection CRUD, history |
| `aircraft-detail-documents.js` | `documentsMixin()` | Document/collection CRUD, viewer |
| `aircraft-detail-major-records.js` | `majorRecordsMixin()` | Major repair/alteration CRUD |
| `aircraft-detail-events.js` | `eventsMixin()` | Recent activity card, history modal |
| `aircraft-detail-roles.js` | `rolesMixin()` | Role management, public sharing toggle |

Composer: `aircraft-detail.js`. **Never use spread (`{...obj}`) to merge mixins** — it eagerly evaluates `get` properties, breaking cross-mixin `this` references. `mergeMixins()` preserves getter descriptors via `Object.getOwnPropertyDescriptors()`.

To add a feature: create `aircraft-detail-<feature>.js`, add to composer and template's `{% block extra_js %}`.

### Shared JS Utilities (`core/static/js/utils.js`, loaded globally via `base.html`)

`getCookie`, `mergeMixins`, `apiRequest` (CSRF+JSON+204 wrapper), `showNotification`, `formatDate`, `formatHours`, `getAirworthinessClass/Text/Tooltip`, `getSquawkPriorityClass`, `formatApiError`

### CSP — No Inline Scripts

**All JS must be external files in `core/static/js/`** — inline `<script>` blocks are blocked by CSP. Load via `<script src="{% static 'js/file.js' %}">`. CDN allowlist: scripts from `cdn.jsdelivr.net`, styles from `unpkg.com`. Adding a new CDN requires updating `nginx-config.yaml` in the gitops repo.

### File Upload Validation

Call `validate_uploaded_file(value)` from `health/serializers.py` in serializer field validators. Checks extension + content type against `ALLOWED_UPLOAD_EXTENSIONS` / `ALLOWED_UPLOAD_CONTENT_TYPES`.

### Serializers

Two patterns:
1. **`HyperlinkedModelSerializer`** — Standard CRUD. **Always include `id` explicitly** (see Gotcha #2).
2. **Nested Serializers** — Embed in responses; include display fields + `read_only_fields`. Serve as both read and write serializers to avoid separate pairs.

### Airworthiness Calculation (`health/services.py`)

`calculate_airworthiness(aircraft)` checks (in order): AD compliance, grounding squawks (priority 0), inspection recurrency, component replacement. Thresholds: overdue = RED; 10 hrs / 30 days warning = ORANGE.

Shared helpers: `ad_compliance_status()`, `inspection_compliance_status()`. Constants: `STATUS_COMPLIANT`, `STATUS_DUE_SOON`, `STATUS_OVERDUE`, `STATUS_LABELS`.

### Event Logging

All writes are logged as `AircraftEvent` records.

- **`log_event(aircraft, category, event_name, user=None, notes="")`** (`core/events.py`)
- **`EventLoggingMixin`** (`core/mixins.py`) — auto-logs create/update/destroy; set `event_category` on viewset; set `aircraft_field` (dot-notation) if Aircraft FK is indirect
- Categories: `hours`, `component`, `squawk`, `note`, `oil`, `fuel`, `logbook`, `ad`, `inspection`, `document`, `aircraft`, `role`, `major_record`
- Acronyms in `verbose_name` get lowercased (e.g. "AD" → "Ad"). Override with `event_name_created`/`event_name_updated`/`event_name_deleted` on the viewset.

API: `GET /api/aircraft/{id}/events/?limit=50&category=hours` → `{ events: [...], total: N }` (max 200).

### Role-Based Access Control (RBAC)

Three roles: **Admin** (`is_staff`/`is_superuser`, bypasses all per-aircraft checks), **Owner**, **Pilot**.

#### Access Matrix

| Action | Admin | Owner | Pilot |
|--------|-------|-------|-------|
| View all data | Yes | Yes | Yes |
| Update hours, create squawks/notes/oil/fuel | Yes | Yes | Yes |
| Edit/delete squawks, notes | Yes | Yes | No |
| CRUD components, logbook, ADs, inspections, documents | Yes | Yes | No |
| Edit/delete aircraft, manage roles & sharing | Yes | Yes | No |
| Create aircraft (auto-assigned owner) | Yes | Yes | Yes |

#### Permission Classes (`core/permissions.py`)

- `get_user_role(user, aircraft)` → `'admin'` | `'owner'` | `'pilot'` | `None`
- `IsAircraftOwnerOrAdmin`, `IsAircraftPilotOrAbove`
- `IsAdAircraftOwnerOrAdmin` — allows AD update/partial_update if user owns any aircraft the AD is associated with
- `PILOT_WRITE_ACTIONS` = `{'update_hours', 'squawks', 'notes', 'oil_records', 'fuel_records'}`
- `PILOT_WRITABLE_MODELS` = `{'squawk', 'consumablerecord', 'aircraftnote'}`

#### AircraftScopedMixin (`core/mixins.py`)

Add as **first** parent (before `EventLoggingMixin`, before `viewsets.ModelViewSet`). Scopes querysets to user's aircraft; enforces role-level write checks. Requires `aircraft_fk_path` class attr (ORM `__` path to Aircraft). Most viewsets use `'aircraft'`; `DocumentImageViewSet` uses `'document__aircraft'`.

#### AircraftViewSet Custom Actions

- `summary` (GET) — aircraft + components + squawks + notes
- `update_hours` (POST) — updates hours, syncs IN-USE components
- `squawks`, `notes`, `oil_records`, `fuel_records`, `components`, `ads`, `compliance`, `inspections`, `major_records` — GET/POST on aircraft
- `manage_roles` (GET/POST/DELETE) — owner-only; user by ID; last-owner + self-removal protection
- `share_tokens` (GET/POST), `share_tokens/<id>` (DELETE) — owner-only; max 10 tokens

#### AircraftViewSet Permission Routing

- `create` → `IsAuthenticated`
- `update`, `destroy`, `components`, `ads`, `compliance`, `inspections`, `major_records`, `manage_roles`, `manage_share_tokens`, `delete_share_token` → `IsAircraftOwnerOrAdmin`
- everything else → `IsAircraftPilotOrAbove`

#### Public Sharing

- `AircraftShareToken`: `token` (UUID, never exposed via API), `label`, `privilege` (`'status'`|`'maintenance'`), `expires_at`. Max 10/aircraft.
- `AircraftNote.public` (bool) — only `public=True` notes visible via share links.
- Routes: `/shared/<uuid>/` (HTML), `/api/shared/<uuid>/` (JSON), `/api/shared/<uuid>/logbook-entries/` (maintenance only).

**Privilege levels:**

| Data | `status` | `maintenance` |
|------|----------|--------------|
| Overview, components, airworthiness, active squawks | Yes | Yes |
| AD/inspection current status + `latest_record`, oil/fuel, public docs/notes | Yes | Yes |
| AD/inspection history, resolved squawks, major records, full logbook | No | Yes |

#### Frontend Role Guards (`aircraft-detail.js` core state)

Getters: `isPublicView`, `isMaintenance`, `userRole`, `isOwner`, `isPilot`, `canWrite`, `canUpdateHours`, `canCreateSquawk`, `canCreateConsumable`, `canCreateNote`. Used via `x-show` in templates. API enforces permissions server-side regardless.

#### Adding RBAC to New ViewSets

```python
class MyViewSet(AircraftScopedMixin, EventLoggingMixin, viewsets.ModelViewSet):
    aircraft_fk_path = 'aircraft'
    event_category = 'my_category'
```
Add to `PILOT_WRITABLE_MODELS` if pilots should write it. Reference-data viewsets (no Aircraft FK) use `IsAuthenticated` reads, `IsAdminUser` writes — **except `ADViewSet`**, which uses `IsAdAircraftOwnerOrAdmin` for `update`/`partial_update` (allows owners of any associated aircraft to edit) and `IsAdminUser` for `create`/`destroy`.

Backfill ownership: `python manage.py assign_owners --user <username> --all`

### OIDC Authentication

Feature flag: `OIDC_ENABLED` env var (default `false`). Library: `mozilla-django-oidc`.

Backends (when enabled): `CustomOIDCAuthenticationBackend` (OIDC first) + `ModelBackend` (fallback — local/admin accounts always work). Username strategy: `preferred_username` → email local part → `sub`. Auto-creates/syncs users on login. Logout (`core.views.custom_logout`) handles both RP-initiated OIDC logout and Django session logout.

Key files: `core/oidc.py`, `core/context_processors.py` (exposes `OIDC_ENABLED` to templates).

Required env vars: `OIDC_RP_CLIENT_ID`, `OIDC_RP_CLIENT_SECRET`, `OIDC_OP_DISCOVERY_ENDPOINT`.

### Logbook Import (Multi-Provider AI)

`health/logbook_import.py`. Providers: `anthropic` (Anthropic SDK, rate-limit retries) and `ollama` (base URL, no retries).

Model registry: `LOGBOOK_IMPORT_MODELS` (list of `{id, name, provider}` dicts). Default: `LOGBOOK_IMPORT_DEFAULT_MODEL`. Add prod-only models via `LOGBOOK_IMPORT_EXTRA_MODELS` JSON env var.

To add a new provider:
1. Add `_call_<provider>()` → returns `{'data', 'truncated', 'output_tokens'}`
2. Add case to `_call_model()` dispatcher
3. Add client creation in `run_import()` and management command `_dry_run()`
4. Add settings to both `settings.py` and `settings_prod.py`

**Batch gotcha**: `_make_batches()` overlaps by 1 page. Batch size 1 skips overlap (infinite loop prevention) — no action needed, just be aware.

## Common Gotchas

### 1. Settings Files

- `settings.py` — dev (SQLite, DEBUG=True)
- `settings_prod.py` — prod; **requires `DJANGO_SECRET_KEY` + `DJANGO_ALLOWED_HOSTS`** env vars (no defaults; crashes intentionally if missing)

Test: `DJANGO_SECRET_KEY=test DJANGO_ALLOWED_HOSTS=localhost python manage.py check --settings=simple_aircraft_manager.settings_prod`

### 2. HyperlinkedModelSerializer Must Include `id`

`HyperlinkedModelSerializer` omits `id` from `__all__` (replaced by `url`). Alpine.js `x-for` with `:key="record.id"` silently renders **zero rows** if `id` is missing. Always include `'id'` in the field list or declare `id = serializers.UUIDField(read_only=True)`.

### 3. CSRF for API Calls

Use `apiRequest()` from `utils.js` for JSON API calls. For `FormData` uploads, use raw `fetch` with `getCookie('csrftoken')` (don't set `Content-Type` manually).

### 4. Spread Operator Breaks Mixin Getters

`{...obj}` eagerly evaluates `get` properties → breaks cross-mixin `this`. Always use `mergeMixins()`.

### 5. Document Collections

Documents have `collection` FK set or `collection=null` (uncollected). Both returned by `/api/aircraft/{id}/documents/`.

### 6. Stacking Modals (PatternFly z-index)

`.pf-v5-c-backdrop` is `z-index: 1000`. A second modal stacked on top needs `style="z-index: 1100;"` — anything ≤ 1000 renders behind regardless of DOM order.

### 7. AircraftSerializer depth=1 and User FKs

`AircraftSerializer` uses `depth = 1`. Any new reverse relation from Aircraft to a model with a `User` FK causes a 500 (DRF tries to generate `user-detail` URL; no endpoint exists). Fix: declare the relation as `PrimaryKeyRelatedField(many=True, read_only=True)` explicitly on `AircraftSerializer`.

### 8. Keep Import/Export in Sync with Model Schema

`core/export.py` and `core/import_export.py` manually map model fields to/from dict keys. They are **not** auto-generated and will silently break if model fields are renamed or replaced. **Whenever a model field is added, renamed, or removed, update both files:**

- `core/export.py` — the `_<model>_dict()` builder function for that model
- `core/import_export.py` — the corresponding `<Model>.objects.create(...)` call

## File Locations

| Purpose | Location |
|---------|----------|
| Django settings | `simple_aircraft_manager/settings.py` |
| Production settings | `simple_aircraft_manager/settings_prod.py` |
| URL routing | `simple_aircraft_manager/urls.py` |
| Airworthiness + status logic | `health/services.py` |
| Upload validation | `health/serializers.py` (`validate_uploaded_file`) |
| Event logging | `core/events.py` (`log_event`) |
| EventLoggingMixin + AircraftScopedMixin | `core/mixins.py` |
| Permission classes | `core/permissions.py` |
| Public sharing views | `core/views.py` |
| Public base template | `core/templates/base_public.html` |
| Logbook import | `health/logbook_import.py` |
| OIDC backend | `core/oidc.py` |
| JS shared utilities | `core/static/js/utils.js` |
| Aircraft detail mixins | `core/static/js/aircraft-detail-*.js` |
| Aircraft detail composer | `core/static/js/aircraft-detail.js` |
| CSS overrides | `core/static/css/app.css` |
| Base template | `core/templates/base.html` |
| **User-facing docs (Sphinx)** | **`docs/user-guide/`** |

## Updating User Documentation

**Whenever a UX change is made, update `docs/user-guide/` to match.**

The user guide is written in reStructuredText (`.rst`) and built with Sphinx. Key files:

| File | Covers |
|------|--------|
| `docs/user-guide/components.rst` | Component tracking, hours columns, service reset modal |
| `docs/user-guide/airworthiness.rst` | Status calculation logic and thresholds |
| `docs/user-guide/squawks.rst` | Squawk priorities and workflow |
| `docs/user-guide/inspections.rst` | Inspection types and compliance |
| `docs/user-guide/ads.rst` | Airworthiness Directives |
| `docs/user-guide/logbook.rst` | Logbook entries and AI import |
| `docs/user-guide/documents.rst` | Document collections and viewer |
| `docs/user-guide/sharing-and-access.rst` | Share links and RBAC |
| `docs/user-guide/oil-and-fuel.rst` | Consumption records and charts |
| `docs/user-guide/major-records.rst` | Major repair/alteration records |

Changes that always require doc updates: new/renamed UI columns, modal workflows, new fields exposed in forms, changed behavior of existing actions, new tab or section added.

## Testing Commands

```bash
python manage.py check
python manage.py check --settings=simple_aircraft_manager.settings_prod
python manage.py runserver
python manage.py makemigrations && python manage.py migrate
```

## API Endpoints

Plural nouns: `/api/aircraft/`, `/api/squawks/`, `/api/aircraft-notes/`, `/api/components/`, `/api/component-types/`, `/api/documents/`, `/api/document-collections/`, `/api/document-images/`, `/api/logbook-entries/`, `/api/inspection-types/`, `/api/inspections/`, `/api/ads/`, `/api/ad-compliances/`, `/api/major-records/`.

Custom actions (snake_case): `update_hours`, `reset_service`, `manage_roles`, `share_tokens`, `delete_share_token`, `major_records`, `summary`, `events`.

Public (no auth): `/shared/<uuid>/`, `/api/shared/<uuid>/`, `/api/shared/<uuid>/logbook-entries/`.
