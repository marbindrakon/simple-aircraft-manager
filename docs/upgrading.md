# Upgrading Simple Aircraft Manager

## v0.9 → v1.0

v1.0 replaces the incremental migration history with a single consolidated
initial migration per app. The database schema is **unchanged** — only the
migration files on disk are different. Because the schema does not change,
rolling back to v0.9 is safe if something goes wrong.

> **If you are running a pre-v0.9 development build, you must upgrade to v0.9
> first and confirm all migrations are applied before proceeding to v1.0.**
> Jumping directly from an older dev build to v1.0 will likely fail because
> the consolidated `0001_initial` migrations assume the full v0.9 schema is
> already present.

**Back up your database before upgrading.** The steps below are low-risk, but
a backup is always good practice before any release upgrade.

### Running management commands

The `manage.py` commands below must be run inside the application. How you do
that depends on your deployment:

- **Local / venv:** run the commands directly in your activated virtualenv.
- **Docker / Podman:** `docker exec -it <container-name> python manage.py <command>`
- **OpenShift / Kubernetes:** `oc exec deploy/sam -n sam -- python manage.py <command>`

### Step 1 — Verify you are fully migrated on v0.9

While still running v0.9, confirm every migration has been applied:

```bash
python manage.py showmigrations core health
```

All entries should show `[X]`. Example of expected output:

```
core
 [X] 0001_initial
 [X] 0002_...
 ...
 [X] 0014_aircraftfeature
health
 [X] 0001_initial
 [X] 0002_...
 ...
 [X] 0031_...
```

If any entry shows `[ ]`, run `python manage.py migrate` with the v0.9 image
to apply the outstanding migrations before proceeding. Skipping this will
cause the v1.0 application to fail with schema errors on every request.

### Step 2 — Upgrade to v1.0

Pull and start the v1.0 image as you normally would, then run:

```bash
python manage.py migrate
```

Because the schema is unchanged, this produces no work to do. Expected output:

```
No migrations to apply.
```

### Step 3 — Confirm the new migration state

```bash
python manage.py showmigrations core health
```

Expected output after the upgrade:

```
core
 [X] 0001_initial
health
 [X] 0001_initial
```

Only the single consolidated initial migration should appear per app. If you
see this, the upgrade is complete.

### Cleaning up orphan migration entries (optional)

The `django_migrations` table still contains the old numbered entries from
v0.9. Django ignores them entirely — they do not appear in `showmigrations`
output — so leaving them in place causes no problems. If you prefer a clean
table, you can remove them:

```bash
python manage.py migrate core --prune
python manage.py migrate health --prune
```

`--prune` removes rows that no longer correspond to a migration file on disk.
It operates on one app at a time, so both apps must be run separately.

---

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
