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
- `aircraft-detail.js` → `aircraftDetail(aircraftId)`
- `hours-update-modal.js` → `hoursUpdateModal()` (loaded globally via `base.html`)
- `squawk-history.js` → `squawkHistory(aircraftId)`

Alpine.js components are initialized via `x-data` attributes in templates.

### Content Security Policy (CSP) — No Inline Scripts

A strict CSP is enforced via nginx security headers. **All JavaScript must be in external `.js` files** — inline `<script>` blocks will be blocked by CSP and will not execute.

When adding new JavaScript:
1. Create a new `.js` file in `core/static/js/`
2. Load it via `<script src="{% static 'js/your-file.js' %}">` in the template
3. For page-specific JS, use the `{% block extra_js %}` block
4. For globally-needed JS (shared components/modals), add to `base.html`

The CSP allows scripts from `'self'` and `cdn.jsdelivr.net`, styles from `'self'` and `unpkg.com`, and `'unsafe-eval'` (required by Alpine.js). If you add a new CDN dependency, the CSP in `nginx-config.yaml` (gitops repo) must be updated.

### File Upload Validation

Squawk attachments are validated by `SquawkCreateUpdateSerializer.validate_attachment()` which checks both file extension and content type against an allowlist (images, PDFs, text). If adding new upload fields, follow the same pattern.

### Serializers: Nested vs Hyperlinked

The codebase uses two serializer patterns:

1. **HyperlinkedModelSerializer** - For standard CRUD endpoints, includes URLs
2. **Nested Serializers** (e.g., `SquawkNestedSerializer`) - For embedding in responses, includes display fields like `priority_display`, `component_name`

When adding new features, create a nested serializer if you need computed/display fields for the frontend.

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

The result is serialized via `AircraftSerializer.get_airworthiness()`.

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

### 2. Component ID in Serializer

The `ComponentSerializer` needs `'id'` explicitly listed in fields (it's not included by default with HyperlinkedModelSerializer).

### 3. CSRF for API Calls

Frontend JavaScript must include CSRF token for POST/PATCH/DELETE:

```javascript
headers: {
    'Content-Type': 'application/json',
    'X-CSRFToken': getCookie('csrftoken'),
}
```

The `getCookie` helper is in `utils.js`.

### 4. Document Collections

Documents can be:
- In a collection (`collection` FK set)
- Uncollected (`collection` is null)

The `/api/aircraft/{id}/documents/` endpoint returns both grouped appropriately.

### 5. OpenShift Arbitrary UIDs

The container runs as arbitrary user IDs in OpenShift. The entrypoint script handles adding the user to `/etc/passwd`. Directories need group write permissions (`chmod g=u`).

### 6. No Inline JavaScript

CSP blocks inline `<script>` tags. All JS must be in external files under `core/static/js/`. See the "Content Security Policy" section above.

### 7. Health Check Endpoint

`/healthz/` is handled directly by nginx (returns 200 JSON without proxying to Django). This avoids `ALLOWED_HOSTS` issues with kube-probe. The Django `healthz` view also exists but is not used by probes.

### 8. TLS Termination

TLS is terminated at the nginx sidecar (port 8443), not at the OpenShift router. The route uses `passthrough` termination. The cert is managed by cert-manager (`certificate.yaml` in gitops). Django receives `X-Forwarded-Proto: https` from nginx and has `SECURE_PROXY_SSL_HEADER` configured to trust it.

## File Locations

| Purpose | Location |
|---------|----------|
| Django settings | `simple_aircraft_manager/settings.py` |
| Production settings | `simple_aircraft_manager/settings_prod.py` |
| URL routing | `simple_aircraft_manager/urls.py` |
| Airworthiness logic | `health/services.py` |
| OIDC backend | `core/oidc.py` |
| Context processors | `core/context_processors.py` |
| Frontend components | `core/static/js/` |
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

The API uses plural nouns for collections:
- `/api/aircraft/` (not aircrafts - aircraft is already plural)
- `/api/squawks/` (plural)
- `/api/aircraft-notes/` (hyphenated)
- `/api/component/` (currently singular - could be made consistent)

Custom actions use snake_case: `update_hours`, `reset_service`
