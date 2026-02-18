# Claude Code Context

This file provides context for Claude instances working on this codebase.

## Project Overview

Simple Aircraft Manager is a Django application for tracking aircraft maintenance, hours, and regulatory compliance. It uses Django REST Framework for APIs and PatternFly + Alpine.js for the frontend.

## Key Concepts

### Hours Tracking Fields on Components

Components have multiple hours-related fields that serve different purposes:

| Field | Purpose | Reset on service? |
|-------|---------|-------------------|
| `hours_in_service` | Hours since last replacement (e.g., oil change) | Yes - for `replacement_critical` components |
| `hours_since_overhaul` | Hours since last overhaul/rebuild | No - only reset on major overhaul |
| `hours_in_service` (total) | Lifetime hours on this component | Never reset |

**Important**: When implementing service resets for consumables (oil, filters), reset `hours_in_service` and `date_in_service`, NOT `hours_since_overhaul`. The `hours_since_overhaul` field is for major component overhauls (engine rebuilds, prop overhauls).

### Component Tracking Flags

Components have three "critical" flags that affect airworthiness:

- `tbo_critical` - Component has a Time Between Overhaul limit (engines, props)
- `inspection_critical` - Component requires periodic inspections
- `replacement_critical` - Component requires periodic replacement (oil, filters, hoses)

For `replacement_critical` components, use `replacement_hours` interval and `hours_in_service` for tracking. For `tbo_critical` components, use `tbo_hours` interval and `hours_since_overhaul`.

### Logbook Entries vs Flight Logs

`LogbookEntry` records are for **maintenance logs**, not per-flight records. They document:
- Maintenance performed
- Inspections completed
- Parts replaced
- Signoffs by mechanics

There is no per-flight journey log feature yet. See TODO.md if it exists for future plans.

### Squawk Priority Levels

```python
SQUAWK_PRIORITIES = (
    (0, "Ground Aircraft"),   # RED - Aircraft cannot fly
    (1, "Fix Soon"),          # ORANGE - Needs attention
    (2, "Fix at Next Inspection"),  # BLUE - Deferred
    (3, "Fix Eventually"),    # GREY - Minor issues
)
```

Priority 0 squawks will ground the aircraft (airworthiness status = RED).

## Architecture Patterns

### Frontend: PatternFly + Alpine.js

The frontend uses:
- **PatternFly 5** CSS framework (loaded from `unpkg.com` CDN)
- **Alpine.js 3** for reactivity (loaded from `cdn.jsdelivr.net`)
- **Chart.js 4** for charts (loaded from `cdn.jsdelivr.net`)
- No build tools required

Each page has a corresponding JavaScript file with an Alpine.js component:
- `dashboard.js` → `aircraftDashboard()`
- `aircraft-detail.js` → `aircraftDetail(aircraftId)` (composer — spreads feature mixins)
- `hours-update-modal.js` → `hoursUpdateModal()` (loaded globally via `base.html`)
- `squawk-history.js` → `squawkHistory(aircraftId)`

Alpine.js components are initialized via `x-data` attributes in templates.

#### Aircraft Detail Mixin Pattern

The aircraft detail page is composed from feature-specific mixin files, each returning a plain object with that feature's state and methods:

| Mixin file | Function | Feature |
|-----------|----------|---------|
| `aircraft-detail-components.js` | `componentsMixin()` | Component CRUD, tree sorting, status |
| `aircraft-detail-squawks.js` | `squawksMixin()` | Squawk CRUD, priority helpers |
| `aircraft-detail-notes.js` | `notesMixin()` | Note CRUD |
| `aircraft-detail-consumables.js` | `makeConsumableMixin(cfg)` | Shared factory for oil/fuel mixins |
| `aircraft-detail-oil.js` | `oilMixin()` | Oil record CRUD, consumption chart (thin wrapper) |
| `aircraft-detail-fuel.js` | `fuelMixin()` | Fuel record CRUD, burn rate chart (thin wrapper) |
| `aircraft-detail-logbook.js` | `logbookMixin()` | Logbook CRUD, file uploads |
| `aircraft-detail-ads.js` | `adsMixin()` | AD CRUD, compliance records, history |
| `aircraft-detail-inspections.js` | `inspectionsMixin()` | Inspection CRUD, history |
| `aircraft-detail-documents.js` | `documentsMixin()` | Document/collection CRUD, viewer |
| `aircraft-detail-major-records.js` | `majorRecordsMixin()` | Major repair/alteration CRUD |
| `aircraft-detail-events.js` | `eventsMixin()` | Recent activity card, history modal |
| `aircraft-detail-roles.js` | `rolesMixin()` | Role management, public sharing toggle |

The composer (`aircraft-detail.js`) merges all mixins using `mergeMixins()` from `utils.js`. **Do not use the spread operator (`...`) for this** — spread eagerly evaluates `get` properties, breaking cross-mixin `this` references. `mergeMixins()` copies property descriptors intact so getters resolve lazily against the final merged object.

When adding a new feature to the aircraft detail page, create a new mixin file following the pattern above and add it to both the composer and the template's `{% block extra_js %}`.

#### Shared JS Utilities (`utils.js`)

Common helpers loaded globally via `base.html`:
- `getCookie(name)` — CSRF token retrieval
- `mergeMixins(...sources)` — Merge objects preserving getter descriptors
- `apiRequest(url, options)` — Fetch wrapper with CSRF, JSON, and 204 handling
- `showNotification(message, type)` — Toast notifications
- `formatDate(dateString)`, `formatHours(hours)` — Display formatting
- `getAirworthinessClass/Text/Tooltip(...)` — Airworthiness badge helpers
- `getSquawkPriorityClass(priority)` — Squawk priority badge helper
- `formatApiError(errorData, fallback)` — API error message formatting

### Content Security Policy (CSP) — No Inline Scripts

A strict CSP is enforced via nginx security headers. **All JavaScript must be in external `.js` files** — inline `<script>` blocks will be blocked by CSP and will not execute.

When adding new JavaScript:
1. Create a new `.js` file in `core/static/js/`
2. Load it via `<script src="{% static 'js/your-file.js' %}">` in the template
3. For page-specific JS, use the `{% block extra_js %}` block
4. For globally-needed JS (shared components/modals), add to `base.html`

The CSP allows scripts from `'self'` and `cdn.jsdelivr.net`, styles from `'self'` and `unpkg.com`, and `'unsafe-eval'` (required by Alpine.js). If you add a new CDN dependency, the CSP in `nginx-config.yaml` (gitops repo) must be updated.

### File Upload Validation

File uploads are validated by `validate_uploaded_file()` in `health/serializers.py`, which checks both file extension and content type against shared allowlists (`ALLOWED_UPLOAD_EXTENSIONS`, `ALLOWED_UPLOAD_CONTENT_TYPES`). This is used by squawk attachments and document images. When adding new upload fields, call `validate_uploaded_file(value)` in your serializer's field validator.

### Serializers: Nested vs Hyperlinked

The codebase uses two serializer patterns:

1. **HyperlinkedModelSerializer** - For standard CRUD endpoints, includes URLs
2. **Nested Serializers** (e.g., `SquawkNestedSerializer`) - For embedding in responses, includes display fields like `priority_display`, `component_name`. These also serve as create/update serializers (with `read_only_fields` for computed fields) to avoid maintaining separate serializer pairs.

When adding new features, create a nested serializer with both display fields and `read_only_fields` rather than separate read/write serializers.

### Custom ViewSet Actions

Aircraft-related operations use custom actions on `AircraftViewSet`:

```python
@action(detail=True, methods=['get'])
def summary(self, request, pk=None):
    # Returns aircraft with components, logs, squawks, notes

@action(detail=True, methods=['post'])
def update_hours(self, request, pk=None):
    # Updates aircraft hours and syncs all IN-USE components

@action(detail=True, methods=['get', 'post'])
def squawks(self, request, pk=None):
    # Get or create squawks for an aircraft

@action(detail=True, methods=['get', 'post'], url_path='major_records')
def major_records(self, request, pk=None):
    # Get or create major repair/alteration records (owner-only for POST)

@action(detail=True, methods=['get', 'post', 'delete'], url_path='manage_roles')
def manage_roles(self, request, pk=None):
    # List, add/update, or remove role assignments (owner-only)

@action(detail=True, methods=['get', 'post'], url_path='share_tokens')
def manage_share_tokens(self, request, pk=None):
    # List or create share tokens (owner-only for POST)

@action(detail=True, methods=['delete'],
        url_path=r'share_tokens/(?P<token_id>[^/.]+)')
def delete_share_token(self, request, pk=None, token_id=None):
    # Revoke a share token by ID (owner-only)
```

### Airworthiness Calculation

The airworthiness status is calculated in `health/services.py`:

```python
def calculate_airworthiness(aircraft) -> AirworthinessStatus:
```

It checks:
1. AD compliance (overdue = RED, due within 10 hrs = ORANGE)
2. Grounding squawks (priority 0 = RED)
3. Inspection recurrency (overdue required = RED, due within 30 days = ORANGE)
4. Component replacement (overdue critical = RED, due within 10 hrs = ORANGE)

The result is serialized via `AircraftSerializer.get_airworthiness()` (provided by `AirworthinessMixin` in `core/serializers.py`).

Individual status checks are also available as shared functions for use outside airworthiness calculation (e.g., in views):
- `ad_compliance_status(ad, compliance, current_hours, today)` → `(rank, extras_dict)`
- `inspection_compliance_status(insp_type, last_record, current_hours, today)` → `(rank, extras_dict)`
- Status constants: `STATUS_COMPLIANT`, `STATUS_DUE_SOON`, `STATUS_OVERDUE`, `STATUS_LABELS`

### Event/Activity Log

All write operations are automatically logged as `AircraftEvent` records, providing an audit trail per aircraft.

#### How It Works

- **`log_event(aircraft, category, event_name, user=None, notes="")`** (`core/events.py`) — single function to create an event record. Called explicitly from views (not via Django signals) so we have access to `request.user` and full context.
- **`EventLoggingMixin`** (`core/mixins.py`) — ViewSet mixin that auto-logs `perform_create`/`perform_update`/`perform_destroy`. Set `event_category` on the viewset class. For models where the Aircraft FK is indirect (e.g., `DocumentImage.document.aircraft`), set `aircraft_field = 'document.aircraft'`.
- **Manual `log_event()` calls** — Used in `AircraftViewSet` custom actions (`update_hours`, `squawks`, `notes`, `oil_records`, `fuel_records`, `components`, `ads`, `compliance`, `inspections`, `major_records`) where the mixin pattern doesn't apply.

#### Categories

Categories are defined in `EVENT_CATEGORIES` in `core/models.py`: `hours`, `component`, `squawk`, `note`, `oil`, `fuel`, `logbook`, `ad`, `inspection`, `document`, `aircraft`, `role`, `major_record`.

#### Event Name Conventions

- Mixin auto-generates names from `model._meta.verbose_name`: "Component created", "Squawk updated", etc.
- **Acronyms like "AD" get lowercased** by `verbose_name.capitalize()` → "Ad compliance created". Override with `event_name_created`/`event_name_updated`/`event_name_deleted` class attributes on the viewset.
- Manual calls in custom actions include context: "Hours updated to 1234.5", "Squawk reported: Fix Soon", "AD linked: 2024-01-01".

#### API

- `GET /api/aircraft/{id}/events/?limit=50&category=hours` — Returns `{ events: [...], total: N }`. Max limit 200.

#### Frontend

The `eventsMixin()` displays:
- **Recent Activity card** on the Overview tab (last 10 events, auto-refreshes after any write via `loadData()`)
- **History modal** with category filter dropdown (up to 200 events)

#### Adding Event Logging to New ViewSets

1. If the viewset is aircraft-scoped, add `AircraftScopedMixin` first, then `EventLoggingMixin`, then `viewsets.ModelViewSet` — e.g., `class MyViewSet(AircraftScopedMixin, EventLoggingMixin, viewsets.ModelViewSet)`. If not aircraft-scoped, add `EventLoggingMixin` as the first parent class.
2. Set `event_category = 'your_category'`
3. If the model's Aircraft FK is not a direct `aircraft` field, set `aircraft_field` (dot-notation for EventLoggingMixin) and `aircraft_fk_path` (double-underscore for AircraftScopedMixin)
4. If `verbose_name` produces wrong casing, set `event_name_created`/`event_name_updated`/`event_name_deleted`

### Logbook Import: Multi-Provider AI

The logbook import system (`health/logbook_import.py`) supports multiple AI providers for transcribing scanned logbook pages. Available models are defined in `LOGBOOK_IMPORT_MODELS` in Django settings.

#### Model Registry

Each entry in `LOGBOOK_IMPORT_MODELS` is a dict with `id`, `name`, and `provider`:

```python
LOGBOOK_IMPORT_MODELS = [
    {'id': 'claude-sonnet-4-5-20250929', 'name': 'Sonnet 4.5 (recommended)', 'provider': 'anthropic'},
    {'id': 'claude-haiku-4-5-20251001', 'name': 'Haiku 4.5 (faster / cheaper)', 'provider': 'anthropic'},
    {'id': 'claude-opus-4-6', 'name': 'Opus 4.6 (highest quality)', 'provider': 'anthropic'},
]
```

`LOGBOOK_IMPORT_DEFAULT_MODEL` sets the default selection. In production, extra models (e.g., Ollama) can be added at deploy time via the `LOGBOOK_IMPORT_EXTRA_MODELS` JSON env var without rebuilding the image.

#### Supported Providers

| Provider | Client | API key required | Retry logic |
|----------|--------|-----------------|-------------|
| `anthropic` | `anthropic.Anthropic` client | Yes (`ANTHROPIC_API_KEY`) | Rate-limit + overload retries with exponential backoff |
| `ollama` | Base URL string (`OLLAMA_BASE_URL`) | No | No retries (local model) |

#### Provider Architecture

- **`run_import()`** — accepts `provider` parameter, creates the appropriate client (Anthropic SDK client or Ollama base URL string)
- **`_extract_all_entries()`** — receives `provider` + `provider_client`, handles adaptive batching and truncation splitting for both providers
- **`_call_model()`** — dispatcher that routes to `_call_anthropic()` or `_call_ollama()`
- **`_call_anthropic()`** — Anthropic Messages API with structured output (`json_schema`), rate-limit retries
- **`_call_ollama()`** — Ollama `/api/chat` endpoint with structured output (`format` field), no retries

All provider functions return the same shape: `{'data': dict, 'truncated': bool, 'output_tokens': int}`

#### Settings

| Setting | Default | Env var | Description |
|---------|---------|---------|-------------|
| `LOGBOOK_IMPORT_MODELS` | 3 Anthropic models | — | Model registry (list of dicts) |
| `LOGBOOK_IMPORT_DEFAULT_MODEL` | `claude-sonnet-4-5-20250929` | `LOGBOOK_IMPORT_DEFAULT_MODEL` | Default model selection |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | `OLLAMA_BASE_URL` | Ollama API base URL |
| `OLLAMA_TIMEOUT` | `1200` | `OLLAMA_TIMEOUT` | Request timeout in seconds for Ollama calls |
| — | — | `LOGBOOK_IMPORT_EXTRA_MODELS` | JSON array of extra model dicts (prod only, additive) |

#### Adding a New Provider

1. Add a `_call_<provider>()` function in `health/logbook_import.py` returning `{'data', 'truncated', 'output_tokens'}`
2. Add a case to `_call_model()` dispatcher
3. Add client creation logic in `run_import()` and the management command's `_dry_run()`
4. Add any new settings to both `settings.py` and `settings_prod.py`

#### Batch Size Gotcha

`_make_batches()` overlaps batches by 1 page to catch cross-page entries. **Batch size 1 skips overlap** — otherwise the index never advances (infinite loop). This is handled automatically; just be aware that batch_size=1 means no cross-page detection.

#### Frontend

The model `<select>` on the import page (`logbook_import.html`) is rendered from `LOGBOOK_IMPORT_MODELS` via template context — not hardcoded in HTML. The JS component reads the default from the rendered select's value in `init()`.

### Authentication: OIDC and Django Hybrid

Simple Aircraft Manager supports both OpenID Connect (OIDC) authentication via Keycloak and traditional Django username/password authentication. Both can coexist, allowing flexible authentication options.

#### Configuration

**Feature Flag**: `OIDC_ENABLED` environment variable (default: `false`)

**Required Environment Variables** (when OIDC enabled):
- `OIDC_RP_CLIENT_ID` - Keycloak client ID (from secret/Vault)
- `OIDC_RP_CLIENT_SECRET` - Keycloak client secret (from secret/Vault)
- `OIDC_OP_DISCOVERY_ENDPOINT` - Keycloak OIDC discovery URL

**Optional Environment Variables**:
- `OIDC_RP_SIGN_ALGO` - Signing algorithm (default: `RS256`)
- `OIDC_RP_SCOPES` - OIDC scopes (default: `openid email profile`)
- `OIDC_EMAIL_CLAIM` - Email claim name (default: `email`)
- `OIDC_FIRSTNAME_CLAIM` - First name claim (default: `given_name`)
- `OIDC_LASTNAME_CLAIM` - Last name claim (default: `family_name`)
- `OIDC_TOKEN_EXPIRY` - Token expiry in seconds (default: `3600`)

**Current Production Config**:
- Keycloak URL: `https://login.home.signal9.gg/realms/signal9`
- Discovery endpoint: `https://login.home.signal9.gg/realms/signal9/.well-known/openid-configuration`
- Client ID: `simple-aircraft-manager` (stored in Vault)

#### Authentication Flow

1. User visits login page and sees "Sign in with Keycloak" button (if OIDC enabled)
2. Click button → redirect to Keycloak → user authenticates
3. Callback to `/oidc/callback/` → Django creates/updates user from OIDC claims
4. User redirected to dashboard with Django session established
5. `SessionRefresh` middleware auto-renews tokens before expiry

**Username Generation Strategy** (priority order):
1. `preferred_username` claim (Keycloak standard)
2. Local part of email address (with uniqueness check)
3. `sub` claim (OIDC subject identifier)

#### Authentication Backends

When OIDC is enabled, Django uses multiple authentication backends in priority order:

```python
AUTHENTICATION_BACKENDS = [
    'core.oidc.CustomOIDCAuthenticationBackend',  # Try OIDC first
    'django.contrib.auth.backends.ModelBackend',   # Fallback to local users
]
```

This allows:
- OIDC users to log in via Keycloak
- Local Django users (like admin) to log in via username/password
- Admin access even if Keycloak is unavailable

#### Logout Behavior

The custom logout view (`core.views.custom_logout`) handles both session types:

- **OIDC session**: Redirects to Keycloak logout endpoint (clears both Django and Keycloak sessions)
- **Django session**: Standard Django logout (redirects to home)

#### User Creation and Sync

**First Login** (OIDC user doesn't exist):
- Django user auto-created from OIDC claims
- Email, first name, last name populated from Keycloak

**Subsequent Logins**:
- User attributes synced from Keycloak on every login
- Keeps local user data in sync with identity provider

#### Keycloak Client Setup Requirements

To integrate with Keycloak, create an OIDC client with these settings:

- **Client ID**: `simple-aircraft-manager`
- **Client Protocol**: `openid-connect`
- **Access Type**: `confidential`
- **Valid Redirect URIs**:
  - `https://sam.apps.oatley.lab.signal9.gg/oidc/callback/`
  - `http://localhost:8000/oidc/callback/` (dev)
- **Valid Post Logout Redirect URIs**:
  - `https://sam.apps.oatley.lab.signal9.gg/`
  - `http://localhost:8000/`
- **Client Scopes**: `openid`, `email`, `profile`
- **Mappers** (verify these exist):
  - `email` → `email` claim
  - `given name` → `given_name` claim
  - `family name` → `family_name` claim
  - `username` → `preferred_username` claim

After creating the client, copy the **Client Secret** from the Credentials tab and store in Vault.

#### Security Considerations

- Client secret stored in Vault (never in ConfigMap)
- OIDC tokens stored in httpOnly Django session cookies
- HTTPS enforced for all OIDC flows
- CSP updated to allow Keycloak form submissions (`form-action 'self' https://login.home.signal9.gg`)
- RP-initiated logout (clears both Django and Keycloak sessions)

#### Troubleshooting

**"OIDC_RP_CLIENT_ID not found" error**:
- Check that `OIDC_ENABLED=true` in ConfigMap
- Verify client ID and secret exist in Vault/ExternalSecret
- Check deployment logs: `oc logs -f deployment/sam -n sam -c sam`

**User redirected to Keycloak but callback fails**:
- Verify redirect URI is registered in Keycloak client settings
- Check that discovery endpoint is accessible from pod
- Look for errors in Django logs during callback

**OIDC button not visible on login page**:
- Verify `OIDC_ENABLED=true` in environment
- Check that context processor is in `TEMPLATES` settings
- Verify `mozilla_django_oidc` is in `INSTALLED_APPS`

**CSP violation when redirecting to Keycloak**:
- Verify `form-action` directive includes Keycloak domain in nginx CSP
- Check browser console for CSP errors

**Admin can't log in after enabling OIDC**:
- Local Django authentication still works (ModelBackend is fallback)
- Use the standard username/password form on login page
- If issues persist, temporarily disable OIDC: set `OIDC_ENABLED=false`

#### Disabling OIDC

To disable OIDC authentication:
1. Set `OIDC_ENABLED=false` in ConfigMap
2. Restart deployment: `oc rollout restart deployment/sam -n sam`
3. Users will see only the Django username/password form

### Role-Based Access Control (RBAC)

Per-aircraft access control with three effective roles: **Admin** (Django `is_staff`/`is_superuser`), **Owner**, and **Pilot**. Admins bypass all per-aircraft checks.

#### Data Model

- **`AircraftRole`** (`core/models.py`) — Links a user to an aircraft with a role (`owner` or `pilot`). Unique constraint on `(aircraft, user)`.
- **`AircraftShareToken`** (`core/models.py`) — A shareable link token tied to an aircraft. Fields: `token` (UUID, unique), `label` (optional), `privilege` (`'status'` or `'maintenance'`), `expires_at` (nullable), `created_by`. Max 10 per aircraft.
- **`AircraftNote.public`** — Boolean flag (default `False`). Only notes with `public=True` are exposed through any share link, regardless of privilege level.
- **`'role'`** event category for audit logging of role changes and sharing actions.

#### Access Matrix

| Action | Admin | Owner | Pilot |
|--------|-------|-------|-------|
| View aircraft & all data | Yes | Yes | Yes |
| Update hours, create squawks/notes/oil/fuel | Yes | Yes | Yes |
| Edit/delete squawks, notes | Yes | Yes | No |
| CRUD components, logbook, ADs, inspections, documents | Yes | Yes | No |
| Edit/delete aircraft, manage roles & sharing | Yes | Yes | No |
| Create new aircraft (becomes owner) | Yes | Yes | Yes |

#### Permission System (`core/permissions.py`)

- **`get_user_role(user, aircraft)`** — Returns `'admin'`, `'owner'`, `'pilot'`, or `None`.
- **`get_user_role_from_prefetch(user, aircraft)`** — Same but uses prefetched `roles` relation.
- **`has_aircraft_permission(user, aircraft, required_role)`** — Hierarchy check using `ROLE_HIERARCHY = {'admin': 3, 'owner': 2, 'pilot': 1}`.
- **`IsAircraftOwnerOrAdmin`** — DRF permission class for owner-level actions.
- **`IsAircraftPilotOrAbove`** — DRF permission class; safe methods allowed for pilot+, unsafe methods require owner+ unless action is in `PILOT_WRITE_ACTIONS`.
- **`PILOT_WRITE_ACTIONS`** — `{'update_hours', 'squawks', 'notes', 'oil_records', 'fuel_records'}`.
- **`PILOT_WRITABLE_MODELS`** — `{'squawk', 'consumablerecord', 'aircraftnote'}` (for standalone viewset writes).

#### AircraftScopedMixin (`core/mixins.py`)

Applied to all standalone aircraft-related viewsets (before `EventLoggingMixin` in MRO). Provides:

1. **Queryset scoping** — Filters to only objects whose aircraft has an `AircraftRole` for the current user (admin sees all).
2. **Object-level permission checks** — Verifies role before allowing writes. Pilot-writable models (`PILOT_WRITABLE_MODELS`) allow pilot writes; everything else requires owner+.

**Required class attribute**: `aircraft_fk_path` — ORM double-underscore path from the model to Aircraft (e.g., `'aircraft'` or `'document__aircraft'`).

| ViewSet | `aircraft_fk_path` |
|---------|-------------------|
| `ComponentViewSet` | `'aircraft'` |
| `SquawkViewSet` | `'aircraft'` |
| `DocumentCollectionViewSet` | `'aircraft'` |
| `DocumentViewSet` | `'aircraft'` |
| `DocumentImageViewSet` | `'document__aircraft'` |
| `LogbookEntryViewSet` | `'aircraft'` |
| `InspectionRecordViewSet` | `'aircraft'` |
| `ADComplianceViewSet` | `'aircraft'` |
| `ConsumableRecordViewSet` | `'aircraft'` |
| `AircraftNoteViewSet` | `'aircraft'` |
| `MajorRepairAlterationViewSet` | `'aircraft'` |

#### AircraftViewSet Permission Routing

`AircraftViewSet.get_permissions()` routes per-action:
- `create` → `IsAuthenticated` (any user; auto-assigned as owner)
- `update`, `destroy`, `components`, `ads`, `compliance`, `inspections`, `major_records`, `manage_roles`, `manage_share_tokens`, `delete_share_token` → `IsAircraftOwnerOrAdmin`
- `update_hours`, `squawks`, `notes`, `oil_records`, `fuel_records` → `IsAircraftPilotOrAbove`
- `list`, `retrieve`, `summary`, `documents`, `events` → `IsAircraftPilotOrAbove`

`get_queryset()` uses `prefetch_related('roles')` and filters to aircraft with an `AircraftRole` for the user.

`perform_create()` wraps aircraft creation + owner role assignment in `transaction.atomic()`.

#### New Custom Actions on AircraftViewSet

- **`manage_roles`** (detail, GET/POST/DELETE) — Owner-only. Safeguards: last-owner protection, self-removal prevention, uniform error responses to prevent user enumeration. Accepts user by ID only (not username).
- **`manage_share_tokens`** (detail, GET/POST, url_path `share_tokens`) — Owner-only. GET lists all tokens; POST creates a new token. Body: `privilege` (required: `'status'`|`'maintenance'`), `label` (optional), `expires_in_days` (optional). Max 10 tokens per aircraft.
- **`delete_share_token`** (detail, DELETE, url_path `share_tokens/<token_id>`) — Owner-only. Revokes the token immediately; the public URL returns 404 thereafter.

#### Public Sharing

- **`/shared/<uuid:token>/`** — `PublicAircraftView` renders read-only template. No login required. Looks up `AircraftShareToken` by `token` field and passes `privilege_level` to template context.
- **`/api/shared/<uuid:token>/`** — `PublicAircraftSummaryAPI` returns JSON summary filtered by privilege level. No CSRF/auth. Strips `has_share_links` and `roles`; sets `user_role=None`.
- **`/api/shared/<uuid:token>/logbook-entries/`** — `PublicLogbookEntriesAPI`. Returns 404 for `status` privilege tokens.
- Token validation: looks up `AircraftShareToken` by `token` field; returns 404 if not found or `expires_at` is in the past.
- Frontend: Uses `aircraftDetail(aircraftId, shareToken, privilegeLevel)` with `base_public.html`. `isPublicView` getter disables write actions; `isMaintenance` getter controls visibility of history, logbook, major records tabs/buttons.

#### Privilege Levels

| Data | `status` | `maintenance` |
|------|----------|--------------|
| Overview, components, airworthiness | Yes | Yes |
| Active squawks | Yes | Yes |
| AD/inspection current status + `latest_record` | Yes | Yes |
| Oil & fuel records, public documents | Yes | Yes |
| Notes (`public=True` only) | Yes | Yes |
| AD compliance history | No | Yes |
| Inspection history | No | Yes |
| Resolved squawks | No | Yes |
| Major repairs & alterations | No | Yes |
| Full logbook (paginated) | No | Yes |
| Linked logbook entries | No | Yes |

#### Serializer Additions

- **`UserRoleMixin`** — Adds `get_user_role()` method, used by both `AircraftSerializer` and `AircraftListSerializer` to expose `user_role` field.
- **`AircraftSerializer`**: Includes `user_role`, `has_share_links` (owner/admin only — `True` if any `AircraftShareToken` exists). `roles` declared as `PrimaryKeyRelatedField` to prevent depth=1 User FK expansion.
- **`AircraftListSerializer`**: Includes `user_role`, `has_share_links`.
- **`AircraftRoleSerializer`** — For `manage_roles` endpoint. Fields: `id`, `user`, `username`, `user_display`, `role`, `created_at`.
- **`AircraftShareTokenSerializer`** — For `manage_share_tokens` endpoint. Fields: `id`, `label`, `privilege`, `expires_at`, `created_at`, `share_url` (computed). `token` UUID is never exposed to the API consumer.

#### Frontend Role Guards

The `aircraft-detail.js` core state object includes `get` properties (preserved by `mergeMixins()`):

```javascript
get isPublicView() { return !!this._publicShareToken; },
get isMaintenance() { return !this.isPublicView || this._privilegeLevel === 'maintenance'; },
get userRole() { return this.aircraft?.user_role || null; },
get isOwner() { return this.userRole === 'owner' || this.userRole === 'admin'; },
get isPilot() { return this.userRole === 'pilot'; },
get canWrite() { return this.isOwner; },
get canUpdateHours() { return this.isOwner || this.isPilot; },
get canCreateSquawk() { return this.isOwner || this.isPilot; },
get canCreateConsumable() { return this.isOwner || this.isPilot; },
get canCreateNote() { return this.isOwner || this.isPilot; },
```

Template buttons use `x-show` directives (`x-show="isOwner"`, `x-show="canUpdateHours"`, etc.) to hide actions the user cannot perform. `isMaintenance` guards the Logbook tab, Repairs & Alterations tab, compliance/inspection history buttons, and resolved squawks section in the public view. The API enforces permissions server-side regardless.

Dashboard cards show a role badge and use `canUpdateHours(aircraft)` to guard the Update Hours button.

#### Backfilling Ownership

After initial deployment, run the management command to assign owners to existing aircraft:

```bash
python manage.py assign_owners --user <username> --all
```

Options: `--all` (all aircraft without an owner) or `--aircraft <tail_numbers>` (specific aircraft).

#### Adding RBAC to New ViewSets

1. Add `AircraftScopedMixin` as the **first** parent class (before `EventLoggingMixin`, before `viewsets.ModelViewSet`)
2. Set `aircraft_fk_path` to the ORM path from the model to Aircraft
3. If the model should be pilot-writable, add its lowercase class name to `PILOT_WRITABLE_MODELS` in `core/permissions.py`
4. Reference-data viewsets (no Aircraft FK) use `IsAuthenticated` for reads, `IsAdminUser` for writes

## Common Gotchas

### 1. Settings Files

- `settings.py` - Development (DEBUG=True, SQLite)
- `settings_prod.py` - Production (env vars, PostgreSQL support)

**Production settings require `DJANGO_SECRET_KEY` and `DJANGO_ALLOWED_HOSTS` env vars** — there are no fallback defaults. The app will crash on startup if they are missing (this is intentional).

To test production settings locally:
```bash
DJANGO_SECRET_KEY=test DJANGO_ALLOWED_HOSTS=localhost python manage.py check --settings=simple_aircraft_manager.settings_prod
```

The Containerfile passes dummy values for `collectstatic` at build time since it doesn't need real secrets.

### 2. HyperlinkedModelSerializer Always Needs Explicit `id`

`HyperlinkedModelSerializer` with `fields = '__all__'` does **not** include the UUID primary key (`id`) in API responses — it's replaced by `url` as the resource identifier. This affects every serializer using `__all__` or any field list that doesn't explicitly name `'id'`.

**Rule**: Every `HyperlinkedModelSerializer` must either:
- Include `'id'` in its explicit field list, **or**
- Declare `id = serializers.UUIDField(read_only=True)` as a class attribute

**Why it matters for the frontend**: Alpine.js `x-for` uses `:key` to track elements. If `:key="record.id"` resolves to `undefined` for all items (because `id` is missing from the API response), Alpine v3 silently renders **zero rows** — not even one. This is an easy bug to miss because the data is present in the Alpine state; only rendering breaks.

**All serializers in this codebase have been fixed** to expose `id`. When adding a new `HyperlinkedModelSerializer`, always include `id` from the start.

### 3. CSRF for API Calls

Frontend JavaScript must include CSRF token for POST/PATCH/DELETE. Use `apiRequest()` from `utils.js` which handles this automatically:

```javascript
const { ok, data } = await apiRequest('/api/squawks/', {
    method: 'POST',
    body: JSON.stringify(payload),
});
```

For `FormData` uploads (where `Content-Type` must not be set manually), use raw `fetch` with `getCookie('csrftoken')`.

### 4. Spread Operator vs Getters in Mixins

**Never use `{...obj}` to merge objects containing `get` properties.** The spread operator eagerly evaluates getters, which breaks cross-mixin `this` references and can crash the entire Alpine component. Use `mergeMixins()` from `utils.js` instead, which preserves getter descriptors via `Object.getOwnPropertyDescriptors()`.

### 5. Document Collections

Documents can be:
- In a collection (`collection` FK set)
- Uncollected (`collection` is null)

The `/api/aircraft/{id}/documents/` endpoint returns both grouped appropriately.

### 6. OpenShift Arbitrary UIDs

The container runs as arbitrary user IDs in OpenShift. The entrypoint script handles adding the user to `/etc/passwd`. Directories need group write permissions (`chmod g=u`).

### 7. No Inline JavaScript

CSP blocks inline `<script>` tags. All JS must be in external files under `core/static/js/`. See the "Content Security Policy" section above.

### 8. Health Check Endpoint

`/healthz/` is handled directly by nginx (returns 200 JSON without proxying to Django). This avoids `ALLOWED_HOSTS` issues with kube-probe. The Django `healthz` view also exists but is not used by probes.

### 9. TLS Termination

TLS is terminated at the nginx sidecar (port 8443), not at the OpenShift router. The route uses `passthrough` termination. The cert is managed by cert-manager (`certificate.yaml` in gitops). Django receives `X-Forwarded-Proto: https` from nginx and has `SECURE_PROXY_SSL_HEADER` configured to trust it.

### 10. Stacking Modals (PatternFly Backdrop z-index)

PatternFly 5's `.pf-v5-c-backdrop` sets `z-index: 1000` via CSS custom property. When a second modal must appear **on top of** a first modal (e.g. logbook modal opening from the compliance modal), the second modal's backdrop needs `style="z-index: 1100;"` (or higher). Setting it to anything ≤ 1000 has no effect — it will render behind the other modal regardless of DOM order.

The logbook entry modal (`logbookModalOpen`) currently has `z-index: 1100` for this reason.

### 11. AircraftSerializer depth=1 and User FKs

`AircraftSerializer` uses `depth = 1`, which auto-expands all FKs on related models. If a related model (like `AircraftEvent` or `AircraftRole`) has a `User` FK, DRF tries to generate a `user-detail` hyperlink — but there's no User API endpoint, causing a 500 error. Fix: explicitly declare the relation field on `AircraftSerializer` (e.g., `events = PrimaryKeyRelatedField(many=True, read_only=True)`, `roles = PrimaryKeyRelatedField(many=True, read_only=True)`) to prevent auto-depth expansion. This applies to any new model with a User FK that's reachable from Aircraft via reverse relations.

## File Locations

| Purpose | Location |
|---------|----------|
| Django settings | `simple_aircraft_manager/settings.py` |
| Production settings | `simple_aircraft_manager/settings_prod.py` |
| URL routing | `simple_aircraft_manager/urls.py` |
| Airworthiness + status logic | `health/services.py` |
| Upload validation | `health/serializers.py` (`validate_uploaded_file`) |
| Shared upload path factory | `core/models.py` (`make_upload_path`) |
| Event logging utility | `core/events.py` (`log_event`) |
| Event logging mixin | `core/mixins.py` (`EventLoggingMixin`) |
| Aircraft scoping mixin | `core/mixins.py` (`AircraftScopedMixin`) |
| Permission classes | `core/permissions.py` |
| Public sharing views | `core/views.py` (`PublicAircraftView`, `PublicAircraftSummaryAPI`) |
| Public base template | `core/templates/base_public.html` |
| Owner backfill command | `core/management/commands/assign_owners.py` |
| Logbook import (AI providers) | `health/logbook_import.py` |
| OIDC backend | `core/oidc.py` |
| Context processors | `core/context_processors.py` |
| JS shared utilities | `core/static/js/utils.js` |
| Aircraft detail mixins | `core/static/js/aircraft-detail-*.js` |
| Aircraft detail composer | `core/static/js/aircraft-detail.js` |
| CSS overrides | `core/static/css/app.css` |
| Base template | `core/templates/base.html` |
| Container config | `Containerfile`, `docker-entrypoint.sh` |

## Testing Commands

```bash
# Check for issues
python manage.py check

# Check production settings
python manage.py check --settings=simple_aircraft_manager.settings_prod

# Run development server
python manage.py runserver

# Create migrations after model changes
python manage.py makemigrations

# Apply migrations
python manage.py migrate
```

## API Endpoint Naming

The API uses plural nouns consistently for all collection endpoints:
- `/api/aircraft/`, `/api/squawks/`, `/api/aircraft-notes/`, `/api/aircraft-events/`
- `/api/components/`, `/api/component-types/`
- `/api/documents/`, `/api/document-collections/`, `/api/document-images/`
- `/api/logbook-entries/`, `/api/inspection-types/`, `/api/inspections/`
- `/api/ads/`, `/api/ad-compliances/`, `/api/major-records/`

Custom actions use snake_case: `update_hours`, `reset_service`, `manage_roles`, `manage_share_tokens`, `delete_share_token`, `major_records`

Public (unauthenticated) endpoints:
- `/shared/<uuid:token>/` — Read-only HTML view (privilege level from token)
- `/api/shared/<uuid:token>/` — Read-only JSON summary (filtered by privilege)
- `/api/shared/<uuid:token>/logbook-entries/` — Paginated logbook (maintenance privilege only)
