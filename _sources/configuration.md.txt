# Configuration

Simple Aircraft Manager is configured via environment variables. Development uses `settings.py` (SQLite, DEBUG=True). Production uses `settings_prod.py`, which requires `DJANGO_SECRET_KEY` and `DJANGO_ALLOWED_HOSTS` — it will crash intentionally if they are missing.

## Required for Production

| Variable | Description | Example |
|----------|-------------|---------|
| `DJANGO_SECRET_KEY` | Django secret key | Random 50+ character string |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated allowed hosts | `app.example.com,localhost` |

Generate a secret key:
```bash
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

## General

| Variable | Default | Description |
|----------|---------|-------------|
| `DJANGO_DEBUG` | `False` | Enable debug mode |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | — | Trusted origins for CSRF (e.g., `https://app.example.com`) |
| `TZ` | `UTC` | Timezone |

## Database

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_ENGINE` | `sqlite3` | `postgresql` or `sqlite3` |
| `DATABASE_NAME` | `aircraft_manager` | Database name |
| `DATABASE_USER` | `postgres` | Database user |
| `DATABASE_PASSWORD` | — | Database password |
| `DATABASE_HOST` | `localhost` | Database host |
| `DATABASE_PORT` | `5432` | Database port |

## Superuser Auto-Creation

| Variable | Default | Description |
|----------|---------|-------------|
| `DJANGO_SUPERUSER_USERNAME` | — | Create superuser on startup if set |
| `DJANGO_SUPERUSER_PASSWORD` | — | Superuser password |
| `DJANGO_SUPERUSER_EMAIL` | `admin@example.com` | Superuser email |

## OIDC Authentication (Optional)

OIDC is disabled by default. Set `OIDC_ENABLED=true` to enable.

| Variable | Default | Description |
|----------|---------|-------------|
| `OIDC_ENABLED` | `false` | Enable OIDC authentication |
| `OIDC_RP_CLIENT_ID` | — | OIDC client ID (required if enabled) |
| `OIDC_RP_CLIENT_SECRET` | — | OIDC client secret (required if enabled) |
| `OIDC_OP_DISCOVERY_ENDPOINT` | — | OIDC discovery endpoint URL |
| `OIDC_RP_SIGN_ALGO` | `RS256` | Token signing algorithm |
| `OIDC_RP_SCOPES` | `openid email profile` | OIDC scopes |
| `OIDC_TOKEN_EXPIRY` | `3600` | Token expiry in seconds |

When enabled, OIDC and local Django accounts coexist. Users are auto-created on first OIDC login using `preferred_username` → email local part → `sub` as the username.

## AI Logbook Import (Optional)

Enables AI-assisted transcription of scanned maintenance logbook pages.

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | Anthropic API key (enables Claude models) |
| `OLLAMA_BASE_URL` | — | Ollama instance URL (enables self-hosted models) |
| `OLLAMA_TIMEOUT` | `1200` | Ollama request timeout in seconds |
| `LOGBOOK_IMPORT_DEFAULT_MODEL` | (built-in) | Default model ID for import |
| `LOGBOOK_IMPORT_EXTRA_MODELS` | — | JSON array of additional model definitions |

`LOGBOOK_IMPORT_EXTRA_MODELS` format:
```json
[{"id": "llama3.2-vision", "name": "Llama 3.2 Vision", "provider": "ollama"}]
```

If neither `ANTHROPIC_API_KEY` nor `OLLAMA_BASE_URL` is set, the logbook import feature is inactive.

## Testing Configuration

Verify production settings without a live database:
```bash
DJANGO_SECRET_KEY=test DJANGO_ALLOWED_HOSTS=localhost python manage.py check --settings=simple_aircraft_manager.settings_prod
```
