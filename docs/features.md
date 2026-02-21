# Features

## Dark Theme

- Light, Dark, and System (follows OS preference) themes available
- Select from the user menu (top-right dropdown)
- Preference is stored in a browser cookie and applied server-side — no flash on page load

## Aircraft Fleet

- Fleet overview with aircraft cards and thumbnail images
- Color-coded airworthiness status badges (Green/Orange/Red)
- Quick access to update hours from the aircraft page
- Issue count summaries per aircraft
- Oil and fuel consumption charts (Chart.js)

## Aircraft Management

Aircraft detail page with tabbed interface:

- **Overview** — Aircraft info, flight hours, and notes
- **Components** — Component list with service intervals and reset functionality
- **Logbook** — Maintenance log entries with AI-assisted import
- **Squawks** — Active and resolved maintenance issues with priority levels
- **ADs** — Airworthiness Directives management with compliance tracking
- **Inspections** — Periodic inspection requirements and history
- **Documents** — Document collections with multi-page image viewer
- **Major Records** — Major repair and alteration records
- **Oil / Fuel** — Consumption records with trend charts

## Component Tracking

- Parent-child hierarchy for nested component relationships
- Component types with consumable flags
- Three independent tracking modes per component:
  - **Replacement** (`replacement_critical`) — periodic replacement via `replacement_hours` + `hours_since_overhaul`
  - **TBO** (`tbo_critical`) — time between overhauls via `tbo_hours` + `hours_since_overhaul`
  - **Inspection** (`inspection_critical`) — requires periodic inspections
- Service reset for replacement-critical components via a modal with two options:
  - **Service in place** — resets OH/SVC hours only; use when the component is inspected, adjusted, or cleaned without being physically replaced
  - **Replace** — resets OH/SVC hours *and* total time in service; use when a new unit is installed (e.g. oil change, new filter)
- Automatic sync of component hours when aircraft hours are updated

## Airworthiness Status

Automatic status calculation with color-coded badges:

- **Red (Grounding)**: Overdue ADs, grounding squawks (priority 0), overdue required inspections, overdue critical component replacements
- **Orange (Caution)**: ADs due within 10 hours, inspections due within 30 days, component replacements due within 10 hours
- **Green**: All checks pass

## Squawk Management

- Priority levels:
  - **Ground Aircraft** (Red) — immediately grounds the aircraft
  - **Fix Soon** (Orange)
  - **Fix at Next Inspection** (Blue)
  - **Fix Eventually** (Grey)
- Link squawks to specific components
- Attachment support (images, PDFs)
- View resolved squawk history

## Airworthiness Directives (ADs)

- Create and edit ADs directly from the aircraft detail page
- Compliance tracking with due dates
- Recurrence support: one-time, hourly, monthly, annually
- Automatic end-of-month due date calculation for monthly/annual recurrence
- Overdue AD detection with airworthiness status impact
- Compliance history per AD

## Inspections

- Define periodic inspection types with intervals (hours and/or days)
- Track compliance records with dates and hours
- Automatic overdue/due-soon detection integrated into airworthiness status
- Inspection history

## Logbook

- Maintenance log entries with hours, dates, and mechanic signoffs
- AI-assisted transcription of scanned logbook pages:
  - **Anthropic** (Claude models, cloud) — requires `ANTHROPIC_API_KEY`
  - **Ollama** (self-hosted) — requires `OLLAMA_BASE_URL`
- File attachment support for logbook pages

## Documents

- Documents organized in collections
- Multi-page document support with thumbnail navigation
- Full-screen image viewing
- Per-collection and per-document visibility controls for public share links:
  - **Private** (lock) — not visible on any share link
  - **All share links** (globe) — visible to both Status and Maintenance tokens
  - **Maintenance only** (wrench) — visible only to Maintenance-level tokens
- Documents in a collection inherit the collection's visibility by default; individual documents can override it

## Notes

- Add timestamped notes to aircraft with author attribution
- Edit and delete notes
- Mark individual notes as **public** to expose them on share links

## Public Sharing

- Owners can create up to 10 share links per aircraft
- Two privilege levels per link:
  - **Current Status** — Overview, airworthiness, active squawks, public notes, current AD/inspection status. No maintenance history.
  - **Maintenance Detail** — Full history including logbook, AD/inspection history, resolved squawks, and major repairs.
- Optional expiration date and label per link
- Revoke individual links without affecting others
- Public views are fully read-only; no account required

## Aircraft Import / Export

Transfer complete aircraft records between Simple Aircraft Manager instances using a `.sam.zip` archive.

### Export

- Available from the **Sharing & Access** tab of the aircraft detail page (owner/admin only)
- Downloads a `.sam.zip` containing `manifest.json` (all aircraft data) plus attached files (pictures, document images, squawk attachments)
- Files missing from storage are noted in the manifest but do not block export

### Import

- **Dashboard** — click the import button next to "New Aircraft" to upload a `.sam.zip`
- Archive is validated before import begins: zip bomb detection, path traversal checks, magic-byte file verification, schema version check, and tail number conflict detection
- If the tail number already exists, you can provide an alternate tail number before confirming
- Import runs in the background; progress and any warnings are shown in the UI
- All internal IDs are remapped — the imported aircraft gets fresh UUIDs
- Rolls back cleanly if an error occurs mid-import

### CLI

```bash
# Export
python manage.py export_aircraft N12345
python manage.py export_aircraft N12345 -o /tmp/n12345.sam.zip

# Import (dry run — validates without creating records)
python manage.py import_aircraft /tmp/n12345.sam.zip --owner alice --dry-run

# Import
python manage.py import_aircraft /tmp/n12345.sam.zip --owner alice
python manage.py import_aircraft /tmp/n12345.sam.zip --owner alice --tail-number N99999
```

See [configuration.md](configuration.md) for `AIRCRAFT_CREATE_PERMISSION` and import size settings.

## Role-Based Access Control

Three roles per aircraft:

| Action | Admin | Owner | Pilot |
|--------|-------|-------|-------|
| View all data | Yes | Yes | Yes |
| Update hours, create squawks/notes/oil/fuel | Yes | Yes | Yes |
| Edit/delete squawks, notes | Yes | Yes | No |
| CRUD components, logbook, ADs, inspections, documents | Yes | Yes | No |
| Edit/delete aircraft, manage roles & sharing | Yes | Yes | No |
| Create / import aircraft | Configurable — see `AIRCRAFT_CREATE_PERMISSION` |

**Admin** = Django staff/superuser, bypasses all per-aircraft checks.

`AIRCRAFT_CREATE_PERMISSION` controls who can create or import aircraft instance-wide:
- `any` (default) — any authenticated user
- `owners` — only users who already own at least one aircraft, plus admins
- `admin` — admins only

## OIDC Authentication

Optional single sign-on via any OIDC-compatible provider (Keycloak, etc.):

- Automatic user provisioning from OIDC claims
- Hybrid authentication — OIDC and local Django accounts coexist
- RP-initiated logout clears both Django and provider sessions
- Feature flag: set `OIDC_ENABLED=true` to enable

See [configuration.md](configuration.md) for required environment variables.

## Oil & Fuel Tracking

- Record oil additions and fuel fills with quantities and hours
- Consumption trend charts (Chart.js)
- Shared mixin architecture for consistent UI

## Major Records

- Track FAA Form 337 major repairs and alterations
- List view on aircraft detail page
- Visible on maintenance-level share links
