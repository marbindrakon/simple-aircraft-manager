# Simple Aircraft Manager - OpenShift Container
# Based on Red Hat UBI 9 Python 3.11
FROM registry.access.redhat.com/ubi9/python-311:latest

# Labels for OpenShift
LABEL name="simple-aircraft-manager" \
      vendor="Simple Aircraft Manager" \
      version="1.0" \
      summary="Aircraft maintenance tracking application" \
      description="Django-based aircraft hours and maintenance tracking system" \
      io.k8s.display-name="Simple Aircraft Manager" \
      io.k8s.description="Django-based aircraft hours and maintenance tracking system" \
      io.openshift.tags="python,django,aircraft,maintenance"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_HOME=/opt/app-root/src \
    DJANGO_SETTINGS_MODULE=simple_aircraft_manager.settings

# Switch to root to install system dependencies
USER 0

# Install system dependencies for Pillow
RUN dnf install -y --nodocs \
    libjpeg-turbo-devel \
    zlib-devel \
    && dnf clean all \
    && rm -rf /var/cache/dnf

# Allow arbitrary UIDs to update /etc/passwd at runtime (OpenShift requirement)
RUN chmod g=u /etc/passwd

# Switch back to default user
USER 1001

# Set working directory
WORKDIR ${APP_HOME}

# Copy requirements first for better layer caching
COPY --chown=1001:0 requirements.txt requirements-prod.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt -r requirements-prod.txt

# Copy application code
COPY --chown=1001:0 . .

# Create directories for data and static files with proper permissions
# OpenShift runs containers with arbitrary user IDs, so we need group write permissions
RUN mkdir -p ${APP_HOME}/staticfiles \
             ${APP_HOME}/mediafiles \
             ${APP_HOME}/data && \
    chmod -R g=u ${APP_HOME}/staticfiles \
                 ${APP_HOME}/mediafiles \
                 ${APP_HOME}/data

# Collect static files
RUN python manage.py collectstatic --noinput --settings=simple_aircraft_manager.settings_prod

# Copy and set up entrypoint script
COPY --chown=1001:0 docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Expose port 8000 (gunicorn; nginx sidecar handles 8080)
EXPOSE 8000

# Set entrypoint and default command
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "4", "simple_aircraft_manager.wsgi:application"]
