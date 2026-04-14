# Upgrading Simple Aircraft Manager

## v0.9 → v1.0

v1.0 replaces the incremental migration history with a single consolidated
initial migration per app. The database schema is **unchanged** — only the
migration files on disk are different.

### Prerequisites

**You must be fully migrated on v0.9 before upgrading.** If your deployment
was behind on migrations (e.g., applied through `health.0020` but not later),
apply all pending migrations with the v0.9 image first:

```bash
python manage.py migrate
```

Then upgrade to v1.0. If you skip this, the running application will see
a schema that does not match its models.

### Standard upgrade

For most deployments, upgrading is no different from any other release:

```bash
# Pull and start the new image as normal, then:
python manage.py migrate
```

`migrate` will produce an empty plan and do nothing — it finds
`('core', '0001_initial')` and `('health', '0001_initial')` already in the
`django_migrations` table from the old chain and skips them. **No special
flags are required.**

### Edge case: empty `django_migrations` table

If you are restoring a database from a schema-only dump (tables exist but
`django_migrations` is empty), use `--fake-initial`:

```bash
python manage.py migrate --fake-initial
```

This marks the initial migrations as applied without re-running DDL.

### Cleaning up orphan migration entries (optional)

After upgrading, the `django_migrations` table will still contain the old
entries (`core.0002` through `core.0014`, `health.0002` through
`health.0031`). Django ignores them — they don't appear in `showmigrations`
output — but they can be confusing when querying the table directly. To
remove them:

```sql
DELETE FROM django_migrations
WHERE app IN ('core', 'health')
  AND name != '0001_initial';
```

### Plugin authors

If you maintain a plugin with migrations that depend on a specific migration
in `core` or `health`, update those dependencies to point to `0001_initial`:

```python
dependencies = [
    ('core', '0001_initial'),  # was ('core', '0014_aircraftfeature') or similar
]
```

Any plugin whose migration references a now-deleted migration name
(e.g. `core.0014_aircraftfeature`) will raise `NodeNotFoundError` when
Django builds the migration graph. The example plugin shipped with this
project has been updated accordingly.
