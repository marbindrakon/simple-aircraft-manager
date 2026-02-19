# Features

## Dashboard

- Fleet overview with aircraft cards and thumbnail images
- Color-coded airworthiness status badges (Green/Orange/Red)
- Quick access to update hours from the dashboard
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
  - **Replacement** (`replacement_critical`) — periodic replacement via `replacement_hours` + `hours_in_service`
  - **TBO** (`tbo_critical`) — time between overhauls via `tbo_hours` + `hours_since_overhaul`
  - **Inspection** (`inspection_critical`) — requires periodic inspections
- One-click service reset for replacement-critical components (e.g., oil changes) — resets `hours_in_service` and `date_in_service`
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
- Documents visible on public share links (based on privilege level)

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

## Role-Based Access Control

Three roles per aircraft:

| Action | Admin | Owner | Pilot |
|--------|-------|-------|-------|
| View all data | Yes | Yes | Yes |
| Update hours, create squawks/notes/oil/fuel | Yes | Yes | Yes |
| Edit/delete squawks, notes | Yes | Yes | No |
| CRUD components, logbook, ADs, inspections, documents | Yes | Yes | No |
| Edit/delete aircraft, manage roles & sharing | Yes | Yes | No |
| Create aircraft (auto-assigned owner) | Yes | Yes | Yes |

**Admin** = Django staff/superuser, bypasses all per-aircraft checks.

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
