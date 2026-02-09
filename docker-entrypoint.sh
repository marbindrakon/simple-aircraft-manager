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
