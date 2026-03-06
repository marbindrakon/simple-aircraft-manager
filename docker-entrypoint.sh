#!/bin/bash
set -e

# OpenShift runs containers with arbitrary user IDs
# Add current user to /etc/passwd if running as arbitrary UID
if ! whoami &> /dev/null; then
    if [ -w /etc/passwd ]; then
        echo "${USER_NAME:-default}:x:$(id -u):0:${USER_NAME:-default} user:${HOME}:/sbin/nologin" >> /etc/passwd
    fi
fi

# Use production settings
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-simple_aircraft_manager.settings_prod}"

# Wait for database if using PostgreSQL
if [ "${DATABASE_ENGINE}" = "postgresql" ]; then
    echo "Waiting for PostgreSQL..."
    while ! python -c "import os, socket; socket.create_connection((os.environ.get('DATABASE_HOST', 'localhost'), int(os.environ.get('DATABASE_PORT', '5432'))), timeout=1)" 2>/dev/null; do
        echo "PostgreSQL is unavailable - sleeping"
        sleep 1
    done
    echo "PostgreSQL is available"
fi

# Install plugin packages if SAM_PLUGIN_PACKAGES is set.
# Format: comma-separated pip install specifiers, e.g.
#   SAM_PLUGIN_PACKAGES="my-sam-plugin==1.2.0,another-plugin>=0.5"
# Packages are installed at startup so plugin static files and migrations
# are available before collectstatic and migrate run.
if [ -n "${SAM_PLUGIN_PACKAGES}" ]; then
    echo "Installing plugin packages: ${SAM_PLUGIN_PACKAGES}"
    # Convert comma-separated list to space-separated for pip
    PLUGIN_PKGS=$(echo "${SAM_PLUGIN_PACKAGES}" | tr ',' ' ')
    pip install --no-cache-dir ${PLUGIN_PKGS}
fi

# Collect static files at startup to pick up plugin static assets.
# Plugins loaded at runtime (via SAM_PLUGIN_DIR or SAM_PLUGIN_PACKAGES) were
# not present at image-build time, so we must re-run collectstatic here.
# The build-time collectstatic in the Containerfile handles the base app;
# this handles runtime-added plugins.
if [ -n "${SAM_PLUGIN_DIR}" ] || [ -n "${SAM_PLUGIN_PACKAGES}" ]; then
    echo "Running collectstatic for plugins..."
    python manage.py collectstatic --noinput
fi

# Run database migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Create superuser if credentials provided and user doesn't exist
# Django's createsuperuser --noinput reads DJANGO_SUPERUSER_USERNAME,
# DJANGO_SUPERUSER_PASSWORD, and DJANGO_SUPERUSER_EMAIL from the environment
# directly — no shell interpolation needed.
if [ -n "${DJANGO_SUPERUSER_USERNAME}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD}" ]; then
    export DJANGO_SUPERUSER_EMAIL="${DJANGO_SUPERUSER_EMAIL:-admin@example.com}"
    echo "Checking for superuser..."
    python manage.py createsuperuser --noinput 2>/dev/null || echo "Superuser already exists"
fi

# Execute the main command
exec "$@"
