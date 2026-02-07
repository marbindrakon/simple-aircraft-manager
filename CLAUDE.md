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
- **PatternFly 5** CSS framework (loaded from CDN)
- **Alpine.js 3** for reactivity (loaded from CDN)
- No build tools required

Each page has a corresponding JavaScript file with an Alpine.js component:
- `dashboard.js` → `aircraftDashboard()`
- `aircraft-detail.js` → `aircraftDetail(aircraftId)`

Alpine.js components are initialized via `x-data` attributes in templates.

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

## Common Gotchas

### 1. Settings Files

- `settings.py` - Development (DEBUG=True, SQLite)
- `settings_prod.py` - Production (env vars, PostgreSQL support)

Always test production settings: `python manage.py check --settings=simple_aircraft_manager.settings_prod`

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

## File Locations

| Purpose | Location |
|---------|----------|
| Django settings | `simple_aircraft_manager/settings.py` |
| Production settings | `simple_aircraft_manager/settings_prod.py` |
| URL routing | `simple_aircraft_manager/urls.py` |
| Airworthiness logic | `health/services.py` |
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
