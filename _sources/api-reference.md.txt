# API Reference

All API endpoints require authentication unless noted. Base path: `/api/`.

## Aircraft

| Endpoint | Methods | Description |
|----------|---------|-------------|
| `/api/aircraft/` | GET, POST | List/create aircraft |
| `/api/aircraft/{id}/` | GET, PUT, PATCH, DELETE | Aircraft detail |
| `/api/aircraft/{id}/summary/` | GET | Aircraft with components, squawks, notes |
| `/api/aircraft/{id}/update_hours/` | POST | Update flight hours (syncs components) |
| `/api/aircraft/{id}/squawks/` | GET, POST | Aircraft squawks |
| `/api/aircraft/{id}/notes/` | GET, POST | Aircraft notes |
| `/api/aircraft/{id}/oil_records/` | GET, POST | Oil consumption records |
| `/api/aircraft/{id}/fuel_records/` | GET, POST | Fuel consumption records |
| `/api/aircraft/{id}/components/` | GET, POST | Aircraft components |
| `/api/aircraft/{id}/ads/` | GET, POST | Airworthiness Directives |
| `/api/aircraft/{id}/compliance/` | GET, POST | AD compliance records |
| `/api/aircraft/{id}/inspections/` | GET, POST | Inspection records |
| `/api/aircraft/{id}/major_records/` | GET, POST | Major repair/alteration records |
| `/api/aircraft/{id}/documents/` | GET | Documents organized by collection |
| `/api/aircraft/{id}/events/` | GET | Audit event log (`?limit=50&category=hours`) |
| `/api/aircraft/{id}/manage_roles/` | GET, POST, DELETE | Per-aircraft role management (owner only) |
| `/api/aircraft/{id}/share_tokens/` | GET, POST | List/create share links (owner only) |
| `/api/aircraft/{id}/share_tokens/{token_id}/` | DELETE | Revoke a share link (owner only) |

## Components

| Endpoint | Methods | Description |
|----------|---------|-------------|
| `/api/components/` | GET, POST | List/create components |
| `/api/components/{id}/` | GET, PUT, PATCH, DELETE | Component detail |
| `/api/components/{id}/reset_service/` | POST | Reset service time (oil changes, etc.) |
| `/api/component-types/` | GET, POST | Component type definitions |
| `/api/component-types/{id}/` | GET, PUT, PATCH, DELETE | Component type detail |

## Maintenance

| Endpoint | Methods | Description |
|----------|---------|-------------|
| `/api/squawks/` | GET, PUT, PATCH, DELETE | Squawk detail operations |
| `/api/aircraft-notes/{id}/` | GET, PATCH, DELETE | Note operations |
| `/api/logbook-entries/` | GET, POST, PUT, PATCH, DELETE | Logbook entries |
| `/api/inspection-types/` | CRUD | Inspection type definitions |
| `/api/inspections/` | CRUD | Inspection records |
| `/api/ads/` | CRUD | Airworthiness Directives |
| `/api/ad-compliances/` | CRUD | AD compliance records |
| `/api/major-records/` | CRUD | Major repair/alteration records |

## Documents

| Endpoint | Methods | Description |
|----------|---------|-------------|
| `/api/document-collections/` | CRUD | Document collections |
| `/api/documents/` | CRUD | Documents |
| `/api/document-images/` | CRUD | Document images (individual pages) |

## Public (No Auth Required)

| Endpoint | Methods | Description |
|----------|---------|-------------|
| `/api/shared/{token}/` | GET | Public aircraft summary (filtered by privilege level) |
| `/api/shared/{token}/logbook-entries/` | GET | Paginated logbook (maintenance privilege only) |

## Web Interface

| URL | Description |
|-----|-------------|
| `/` | Redirects to dashboard |
| `/dashboard/` | Fleet dashboard |
| `/aircraft/{id}/` | Aircraft detail page |
| `/shared/{token}/` | Public read-only aircraft view (no login required) |
| `/admin/` | Django admin interface |
| `/accounts/login/` | Login page |

## Event Log

`GET /api/aircraft/{id}/events/` returns `{ events: [...], total: N }`.

Query parameters:
- `limit` — max results, up to 200 (default 50)
- `category` — filter by category: `hours`, `component`, `squawk`, `note`, `oil`, `fuel`, `logbook`, `ad`, `inspection`, `document`, `aircraft`, `role`, `major_record`

## Logbook Import (AI)

| Endpoint | Methods | Description |
|----------|---------|-------------|
| `/api/logbook-import/models/` | GET | Available AI models |
| `/api/logbook-import/` | POST | Submit scanned page image for transcription |
