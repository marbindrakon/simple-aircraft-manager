- Feature: Add wish list tracking function using N1017G spreadsheet as a template for data model and UI
- Feature: Add STC information to the Aircraft Details page including the ability to add, edit, and remove STCs
- Feature: Add the ability to flag a lobook entry as a "Major Repair." Those entries should have a separate display in the Logbook entries tab of the aircraft details page

## Security Review (2026-02-14)

Reviewed all changes from commits d56a7f4..f922fd2 (past 3 days). No HIGH severity issues found. MEDIUM and LOW findings below.

### MEDIUM

- ~~Security: `showNotification()` in `utils.js` interpolates the `message` param into `innerHTML`, creating an XSS vector if server error messages contain user input. Switch to `textContent` for the message element.~~ **FIXED** (2026-02-17)
- ~~Security: No explicit file upload size limit in `validate_uploaded_file()` (`health/serializers.py`). Django defaults allow large files. Add a max size check (e.g., 10 MB).~~ **FIXED** (2026-02-17, 512 MB limit)
- ~~Security: `AircraftEventViewSet` (`/api/aircraft-events/`) has no pagination. As events accumulate this could return thousands of records. Add `pagination_class` or remove the endpoint (frontend uses the scoped `/api/aircraft/{id}/events/` instead).~~ **FIXED** (2026-02-17, page_size=100 max=200)
- ~~Security: No object-level authorization on any ViewSet — any authenticated user can CRUD any aircraft's data. Acceptable for single-tenant use; document this assumption. If multi-tenancy is ever needed, add object-level permissions.~~ **RESOLVED** — Full RBAC (AircraftScopedMixin + roles) was implemented.

### LOW

- ~~Security: `category` query param on `/api/aircraft/{id}/events/` is not validated against `EVENT_CATEGORIES`. Invalid values silently return empty results instead of 400.~~ **FIXED** (2026-02-17)
- ~~Security: Bare `except:` in `update_hours` (core/views.py) catches all exceptions including `SystemExit`. Narrow to `except (ValueError, InvalidOperation, TypeError):`.~~ **FIXED** (2026-02-17)
- ~~Security: `ad_id` and `inspection_type_id` from request data are not pre-validated as UUIDs before DB lookup, producing ugly 500s on invalid input.~~ **FIXED** (2026-02-17, added `ValueError` to all four except clauses)
- Security: File upload content-type is client-supplied and can be spoofed. Extension check mitigates most risk. Consider `python-magic` for defense in depth.
- ~~Security: Event serializers expose raw `user` FK (integer PK) alongside `user_display`. Remove `user` field if only the display name is needed by the frontend.~~ **FIXED** (2026-02-17)
- ~~Security: `_resolve_aircraft()` in `EventLoggingMixin` raises `AttributeError` if any link in the dotted FK path is `None`. Wrap in try/except returning `None` to skip logging gracefully instead of 500ing the operation.~~ **FIXED** (2026-02-17)
