# Per-Aircraft Feature Flags

Simple Aircraft Manager supports per-aircraft feature flags that allow individual features to be enabled or disabled independently — either globally by an administrator or per aircraft by the aircraft owner.

## Overview

Feature flags control which tabs, cards, and actions are visible for a given aircraft. All features are **enabled by default**. Disabling a feature:

- Hides the corresponding UI section (tab, card, or button) for that aircraft
- Enforces the restriction at the API level — the server rejects requests for disabled features
- Affects all users of that aircraft (owner, pilots, share link viewers)

## Known Features

| Feature key | Controls |
|-------------|---------|
| `flight_tracking` | Flights tab and the **Log Flight** button in the aircraft header |
| `oil_consumption` | Oil sub-tab under the Health tab (records and consumption chart) |
| `fuel_consumption` | Fuel sub-tab under the Health tab (records and burn-rate chart) |
| `oil_analysis` | Oil Analysis sub-tab (lab report tracking and trend charts) |
| `airworthiness_enforcement` | Blocks **Log Flight** and **Update Hours** when aircraft is RED/grounded |
| `sharing` | Share Links card on the Settings tab; existing share links stop working when disabled |

## Resolution Order

`feature_available(feature_name, aircraft)` in `core/features.py` resolves flags in this order:

1. **Global kill switch** — if `feature_name` is in the `DISABLED_FEATURES` setting, returns `False` regardless of per-aircraft settings.
2. **Per-aircraft override** — if an `AircraftFeature` row exists for this aircraft and feature, returns its `enabled` field.
3. **Default** — returns `True` (all features on).

## Global Disable (Administrator)

Set the `DISABLED_FEATURES` environment variable to a comma-separated list of feature keys:

```
DISABLED_FEATURES=oil_analysis,fuel_consumption
```

In `settings.py` / `settings_prod.py` this maps to a `DISABLED_FEATURES` list. Features listed here are disabled for **all** aircraft and cannot be re-enabled by owners.

See [configuration.md](configuration.md) for the full environment variable reference.

## Per-Aircraft Toggle (Owner)

Aircraft owners can toggle features from the **Settings** tab of the aircraft detail page. Changes take effect immediately. The UI shows a toggle switch per feature; features that are globally disabled are hidden from this list.

### API

```
GET  /api/aircraft/{id}/features/
POST /api/aircraft/{id}/features/
```

**GET** returns the current state of all known features for the aircraft (including defaults for features that have no row in the database).

**POST** body:

```json
{"feature": "oil_analysis", "enabled": false}
```

Pilots can read feature state (GET). Only owners and admins can write (POST).

## Data Model

`AircraftFeature` in `core/models.py`:

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `aircraft` | FK → Aircraft | The aircraft this flag applies to |
| `feature` | CharField(50) | Feature key (see Known Features table above) |
| `enabled` | BooleanField | `True` = on, `False` = off |
| `updated_at` | DateTimeField | Last modification timestamp (auto) |
| `updated_by` | FK → User | User who last changed the flag |

`unique_together = ('aircraft', 'feature')` — one row per aircraft/feature pair. Missing rows are treated as enabled (the default).

## Checking Feature State in Code

```python
from core.features import feature_available

# Check without a specific aircraft (global kill switch only)
if feature_available('oil_analysis'):
    ...

# Check for a specific aircraft (full resolution)
if feature_available('oil_analysis', aircraft=aircraft_instance):
    ...
```

Use this helper in views, serializers, and services. Do not query `AircraftFeature` directly — the helper handles the global override and default fallback.

## Checking Feature State in Frontend (Alpine.js)

Feature state is loaded as part of the aircraft detail page data and exposed as reactive getters in `aircraft-detail.js`:

| Getter | Feature key |
|--------|-------------|
| `featureFlightTracking` | `flight_tracking` |
| `featureOilConsumption` | `oil_consumption` |
| `featureFuelConsumption` | `fuel_consumption` |
| `featureOilAnalysis` | `oil_analysis` |
| `featureAirworthinessEnforcement` | `airworthiness_enforcement` |
| `featureSharing` | `sharing` |

Use these with `x-show` in templates:

```html
<div x-show="featureOilAnalysis">...</div>
```

## Adding a New Feature Flag

1. Add the feature key string to `KNOWN_FEATURES` in `core/models.py`.
2. Add a row to the Known Features table in `docs/user-guide/sharing-and-access.rst` (user docs).
3. Add a row to the Known Features table in this file.
4. Add a reactive getter to `aircraft-detail.js` (follow the existing pattern).
5. Use `feature_available(key, aircraft)` in any API view or service that should respect the flag.
6. Use `x-show="featureXxx"` in templates to conditionally show the UI.
7. Update `docs/features.md` if the feature is end-user-visible.
