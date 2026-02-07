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
    while ! python -c "import socket; socket.create_connection(('${DATABASE_HOST:-localhost}', ${DATABASE_PORT:-5432}), timeout=1)" 2>/dev/null; do
        echo "PostgreSQL is unavailable - sleeping"
        sleep 1
    done
    echo "PostgreSQL is available"
fi

# Run database migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Create superuser if credentials provided and user doesn't exist
if [ -n "${DJANGO_SUPERUSER_USERNAME}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD}" ]; then
    echo "Checking for superuser..."
    python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='${DJANGO_SUPERUSER_USERNAME}').exists():
    User.objects.create_superuser(
        '${DJANGO_SUPERUSER_USERNAME}',
        '${DJANGO_SUPERUSER_EMAIL:-admin@example.com}',
        '${DJANGO_SUPERUSER_PASSWORD}'
    )
    print('Superuser created')
else:
    print('Superuser already exists')
"
fi

# Execute the main command
exec "$@"
