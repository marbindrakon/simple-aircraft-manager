# Simple Aircraft Manager

> **Note**: This codebase was generated with [Claude](https://claude.ai), Anthropic's AI assistant, using [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

A Django-based web application for managing aircraft fleet operations, maintenance records, and regulatory compliance tracking.

## Overview

Simple Aircraft Manager is a comprehensive fleet management system designed for aircraft operators. It provides tools to track aircraft inventory, maintenance schedules, component lifecycles, compliance with airworthiness directives, and detailed logbook entries.

## Technology Stack

### Backend
- **Django 4.2.9** - Web framework
- **Django REST Framework 3.14.0** - RESTful API
- **django-filter 23.5** - Advanced filtering for querysets
- **Pillow** - Image handling for documents and media
- **Gunicorn** - Production WSGI server
- **WhiteNoise** - Static file serving
- **SQLite** - Database (development)
- **PostgreSQL** - Database (production)
- **Python 3.11** - Programming language

### Frontend
- **PatternFly 5.3.1** - Enterprise UI framework
- **Alpine.js 3.x** - Lightweight reactive framework (3KB)
- **Font Awesome** - Icons

### Deployment
- **Red Hat UBI 9** - Container base image
- **OpenShift** - Container platform

## Features

### Dashboard
- Fleet overview with aircraft cards
- Color-coded airworthiness status badges (Green/Orange/Red)
- Quick access to update hours
- Issue count summaries

### Aircraft Detail Page
- **Overview Tab** - Aircraft info, flight hours, and notes
- **Components Tab** - Component list with service intervals and reset functionality
- **Logbook Tab** - Maintenance log entries
- **Squawks Tab** - Active maintenance issues with priority levels
- **Documents Tab** - Document collections with image viewer

### Airworthiness Status
Automatic status calculation based on:
- **Grounding (Red)**: Overdue ADs, grounding squawks, overdue required inspections, overdue critical component replacements
- **Caution (Orange)**: ADs due within 10 hours, inspections due within 30 days, component replacements due within 10 hours

### Hours Management
- Update aircraft flight hours from dashboard or detail page
- Automatic sync to all in-service components
- Validation prevents hours from decreasing

### Squawk Management
- Create, edit, and resolve maintenance squawks
- Priority levels: Ground Aircraft, Fix Soon, Fix at Next Inspection, Fix Eventually
- Link squawks to specific components
- View resolved squawk history

### Notes
- Add notes to aircraft from the Overview tab
- Edit and delete notes
- View all notes with timestamps and authors

### Component Service Reset
- One-click service reset for replacement-critical components (e.g., oil changes)
- Resets hours_in_service to 0 and updates date_in_service
- Visual indicator for replacement-critical components

### Document Viewer
- Documents organized in collections
- Multi-page document support with thumbnail navigation
- Full-screen image viewing

## Project Structure

```
simple-aircraft-manager/
├── simple_aircraft_manager/     # Main project configuration
│   ├── settings.py              # Development settings
│   ├── settings_prod.py         # Production settings
│   ├── urls.py                  # URL routing
│   ├── wsgi.py                  # WSGI entry point
│   └── asgi.py                  # ASGI entry point
├── core/                        # Core aircraft management
│   ├── models.py                # Aircraft, AircraftNote, AircraftEvent
│   ├── views.py                 # API ViewSets and template views
│   ├── serializers.py           # DRF serializers
│   ├── templates/               # Web templates
│   │   ├── base.html            # Base template with PatternFly
│   │   ├── dashboard.html       # Fleet dashboard
│   │   ├── aircraft_detail.html # Aircraft detail with tabs
│   │   ├── squawk_history.html  # Resolved squawks view
│   │   └── includes/            # Reusable template components
│   └── static/                  # Static assets
│       ├── css/app.css          # Custom styles
│       └── js/                  # Alpine.js components
├── health/                      # Maintenance & compliance
│   ├── models.py                # Maintenance-related models
│   ├── views.py                 # API ViewSets
│   ├── serializers.py           # DRF serializers
│   └── services.py              # Airworthiness calculation
├── Containerfile                # OpenShift container definition
├── docker-entrypoint.sh         # Container startup script
├── requirements.txt             # Development dependencies
└── requirements-prod.txt        # Production dependencies
```

## API Endpoints

All API endpoints require authentication and are accessible at `/api/`.

### Aircraft Endpoints

| Endpoint | Methods | Description |
|----------|---------|-------------|
| `/api/aircraft/` | GET, POST | List/create aircraft |
| `/api/aircraft/{id}/` | GET, PUT, PATCH, DELETE | Aircraft detail operations |
| `/api/aircraft/{id}/summary/` | GET | Aircraft with components, logs, squawks, notes |
| `/api/aircraft/{id}/update_hours/` | POST | Update flight hours (syncs components) |
| `/api/aircraft/{id}/documents/` | GET | Documents organized by collection |
| `/api/aircraft/{id}/squawks/` | GET, POST | Aircraft squawks |
| `/api/aircraft/{id}/notes/` | GET, POST | Aircraft notes |
| `/api/aircraft-notes/{id}/` | GET, PATCH, DELETE | Note operations |

### Component Endpoints

| Endpoint | Methods | Description |
|----------|---------|-------------|
| `/api/component/` | GET, POST | List/create components |
| `/api/component/{id}/` | GET, PUT, PATCH, DELETE | Component operations |
| `/api/component/{id}/reset_service/` | POST | Reset service time (for oil changes, etc.) |
| `/api/component-type/` | CRUD | Component type definitions |

### Maintenance Endpoints

| Endpoint | Methods | Description |
|----------|---------|-------------|
| `/api/squawks/` | CRUD | Maintenance squawks |
| `/api/logbook/` | CRUD | Logbook entries |
| `/api/inspection-type/` | CRUD | Inspection type definitions |
| `/api/inspection/` | CRUD | Inspection records |
| `/api/ad/` | CRUD | Airworthiness Directives |
| `/api/ad-compliance/` | CRUD | AD compliance records |
| `/api/stc/` | CRUD | STC applications |

### Document Endpoints

| Endpoint | Methods | Description |
|----------|---------|-------------|
| `/api/document-collection/` | CRUD | Document collections |
| `/api/document/` | CRUD | Documents |
| `/api/document-image/` | CRUD | Document images |

### Web Interface

| URL | Description |
|-----|-------------|
| `/` | Redirects to dashboard |
| `/dashboard/` | Fleet dashboard |
| `/aircraft/{id}/` | Aircraft detail page |
| `/aircraft/{id}/squawks/history/` | Resolved squawks history |
| `/admin/` | Django admin interface |
| `/accounts/login/` | Login page |

## Installation

### Local Development

1. **Clone the repository**
   ```bash
   cd /path/to/simple-aircraft-manager
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run migrations**
   ```bash
   python manage.py migrate
   ```

5. **Create a superuser**
   ```bash
   python manage.py createsuperuser
   ```

6. **Run the development server**
   ```bash
   python manage.py runserver
   ```

7. **Access the application**
   - Web Interface: http://localhost:8000/dashboard/
   - Admin Interface: http://localhost:8000/admin/
   - API Root: http://localhost:8000/api/

### Container Deployment (OpenShift)

1. **Build the container**
   ```bash
   podman build -t aircraft-manager -f Containerfile .
   ```

2. **Run locally for testing**
   ```bash
   podman run -p 8080:8080 \
     -e DJANGO_SECRET_KEY=your-secret-key \
     -e DJANGO_ALLOWED_HOSTS=localhost \
     aircraft-manager
   ```

3. **Deploy to OpenShift**
   ```bash
   # Create a new app from the container image
   oc new-app --name=aircraft-manager \
     --docker-image=your-registry/aircraft-manager:latest

   # Set environment variables
   oc set env deployment/aircraft-manager \
     DJANGO_SECRET_KEY=your-secret-key \
     DJANGO_ALLOWED_HOSTS=your-route-hostname \
     DJANGO_CSRF_TRUSTED_ORIGINS=https://your-route-hostname

   # Expose the service
   oc expose svc/aircraft-manager
   ```

## Environment Variables

### Required for Production

| Variable | Description | Example |
|----------|-------------|---------|
| `DJANGO_SECRET_KEY` | Django secret key | Random 50+ character string |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated allowed hosts | `app.example.com,localhost` |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `DJANGO_DEBUG` | `False` | Enable debug mode |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | - | Trusted origins for CSRF |
| `DATABASE_ENGINE` | `sqlite3` | `postgresql` or `sqlite3` |
| `DATABASE_NAME` | `aircraft_manager` | Database name |
| `DATABASE_USER` | `postgres` | Database user |
| `DATABASE_PASSWORD` | - | Database password |
| `DATABASE_HOST` | `localhost` | Database host |
| `DATABASE_PORT` | `5432` | Database port |
| `DJANGO_SUPERUSER_USERNAME` | - | Auto-create superuser |
| `DJANGO_SUPERUSER_PASSWORD` | - | Superuser password |
| `DJANGO_SUPERUSER_EMAIL` | `admin@example.com` | Superuser email |
| `TZ` | `UTC` | Timezone |

## Database Models

### Core App

- **Aircraft** - Central fleet inventory (UUID primary key)
- **AircraftNote** - Notes attached to aircraft with timestamps
- **AircraftEvent** - Audit trail of aircraft events

### Health App

- **ComponentType** - Component categories (consumable flag)
- **Component** - Parts with TBO, inspection, and replacement tracking
- **DocumentCollection** - Logical document groupings
- **Document** - Maintenance documentation by type
- **DocumentImage** - Individual pages/images within documents
- **LogbookEntry** - Flight and maintenance logs with hours tracking
- **Squawk** - Maintenance defects with priority levels
- **InspectionType** - Recurring inspection requirements
- **InspectionRecord** - Inspection completion records
- **AD** - Airworthiness Directives with recurrence
- **ADCompliance** - AD compliance tracking
- **STCApplication** - STC tracking

## Data Model Relationships

```
Aircraft (central hub)
├── AircraftNote (1:N)
├── AircraftEvent (1:N)
├── Component (1:N)
│   ├── ComponentType (N:1)
│   ├── Parent Component (self-reference)
│   ├── Squawk (1:N)
│   └── LogbookEntry (M:N)
├── Squawk (1:N)
├── Document (1:N)
├── DocumentCollection (1:N)
├── InspectionRecord (1:N)
└── AD/STC (M:N via compliance tables)
```

## Use Cases

1. **Fleet Operators** - Track multiple aircraft, status, and availability
2. **Maintenance Teams** - Log repairs, inspections, and component changes
3. **Quality Assurance** - Ensure compliance with ADs and inspection requirements
4. **Records Management** - Organize and maintain aircraft logbooks and documentation
5. **Component Tracking** - Monitor component lifecycles and service intervals

## Contributing

When contributing to this project:

1. Review the existing code structure and follow Django best practices
2. Run migrations after model changes: `python manage.py makemigrations`
3. Update API serializers when modifying models
4. Register new models in admin.py for admin interface access
5. Follow the UUID primary key pattern for new models
6. Test with production settings: `python manage.py check --settings=simple_aircraft_manager.settings_prod`

## License

[Add license information here]

## Contact

[Add contact information here]
