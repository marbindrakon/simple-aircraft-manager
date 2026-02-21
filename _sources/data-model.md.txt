# Data Model

## Core App

| Model | Description |
|-------|-------------|
| `Aircraft` | Central fleet inventory (UUID primary key) |
| `AircraftNote` | Notes attached to aircraft with timestamps; `public` flag controls share-link visibility |
| `AircraftEvent` | Audit trail of all changes to aircraft data |
| `AircraftRole` | Per-aircraft user roles (`owner` or `pilot`) |
| `AircraftShareToken` | Share link tokens with privilege level (`status` or `maintenance`), optional expiry, and optional label |

## Health App

| Model | Description |
|-------|-------------|
| `ComponentType` | Component categories (consumable flag) |
| `Component` | Parts with TBO, inspection, and replacement tracking; supports parent-child hierarchy |
| `DocumentCollection` | Logical document groupings |
| `Document` | Maintenance documentation by type |
| `DocumentImage` | Individual pages/images within documents |
| `LogbookEntry` | Maintenance log entries with hours, dates, and file attachments |
| `Squawk` | Maintenance defects with priority levels and optional component link |
| `InspectionType` | Recurring inspection requirements with hour/day intervals |
| `InspectionRecord` | Inspection completion records |
| `AD` | Airworthiness Directives with recurrence settings |
| `ADCompliance` | AD compliance records |
| `MajorRecord` | Major repair and alteration records |
| `ConsumeableRecord` | Oil/fuel consumption records |

## Relationships

```
Aircraft (central hub)
├── AircraftNote (1:N)
├── AircraftEvent (1:N)
├── AircraftRole (1:N) → User
├── AircraftShareToken (1:N)
├── Component (1:N)
│   ├── ComponentType (N:1)
│   ├── Parent Component (self-reference)
│   └── Squawk (1:N, optional link)
├── Squawk (1:N)
├── LogbookEntry (1:N)
├── Document (1:N)
│   ├── DocumentCollection (N:1, optional)
│   └── DocumentImage (1:N)
├── InspectionType (1:N)
├── InspectionRecord (1:N)
├── AD (1:N)
├── ADCompliance (1:N) → AD
├── MajorRecord (1:N)
└── ConsumeableRecord (1:N)
```

## Component Hours Fields

| Field | Purpose | Reset on service? |
|-------|---------|-------------------|
| `hours_in_service` | Hours since last replacement | Yes — `replacement_critical` only |
| `hours_since_overhaul` | Hours since last overhaul/rebuild | No — only on major overhaul |

## Component Critical Flags

| Flag | Tracked via | Purpose |
|------|-------------|---------|
| `replacement_critical` | `replacement_hours` + `hours_in_service` | Periodic replacement (oil, filters) |
| `tbo_critical` | `tbo_hours` + `hours_since_overhaul` | Time between overhauls (engines, props) |
| `inspection_critical` | `InspectionType` records | Requires periodic inspections |

## Squawk Priorities

| Value | Label | Color |
|-------|-------|-------|
| 0 | Ground Aircraft | Red |
| 1 | Fix Soon | Orange |
| 2 | Fix at Next Inspection | Blue |
| 3 | Fix Eventually | Grey |

## Share Token Privilege Levels

| Level | Data Visible |
|-------|-------------|
| `status` | Overview, airworthiness, active squawks, public notes, current AD/inspection status, oil/fuel, documents marked "All share links" |
| `maintenance` | Everything in `status` + full history (logbook, AD/inspection history, resolved squawks, major records) + documents marked "Maintenance only" |
