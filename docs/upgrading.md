# Upgrading Simple Aircraft Manager

## v0.9 → v1.0

v1.0 replaces the incremental migration history with a single consolidated
initial migration per app. **New installations are unaffected.** Existing
deployments need one extra step to reconcile the database state.

### Why

The old migration chain (34 migrations across `core` and `health`) was
squashed into a single `0001_initial` for each app. The database schema is
identical; only the migration records in `django_migrations` are changing.

### Upgrade steps

1. **Back up your database** before proceeding.

2. Pull and deploy the v1.0 image as normal.

3. Before (or immediately after) starting the new container, fake-apply the
   new initial migrations so Django knows the schema is already in place:

   ```bash
   python manage.py migrate --fake-initial
   ```

   `--fake-initial` tells Django: "if the tables for this migration already
   exist, mark it as applied without running the DDL." It will not touch your
   data or schema.

4. Start (or restart) the application. Normal startup proceeds from here.

### What `--fake-initial` does

Django records applied migrations in the `django_migrations` table. After the
zap, that table still contains the old entries (`core.0001_initial` through
`core.0014_aircraftfeature`, etc.) but the new migration files are just
`0001_initial` for each app. `--fake-initial` inserts the new entries without
executing the SQL, leaving your schema and data untouched.

### Verifying the upgrade

```bash
python manage.py showmigrations
```

Both `core` and `health` should show a single `[X] 0001_initial` entry.

### Container / Kubernetes deployments

If you run the migration step as a Kubernetes init container or job, add
`--fake-initial` to that command for this release only:

```yaml
command: ["python", "manage.py", "migrate", "--fake-initial"]
```

Remove the flag after the one-time upgrade is complete.
