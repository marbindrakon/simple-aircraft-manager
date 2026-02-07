# Simple Aircraft Manager

A Django-based web application for managing aircraft fleet operations, maintenance records, and regulatory compliance tracking.

## Overview

Simple Aircraft Manager is a comprehensive fleet management system designed for aircraft operators. It provides tools to track aircraft inventory, maintenance schedules, component lifecycles, compliance with airworthiness directives, and detailed logbook entries.

## Technology Stack

### Backend
- **Django 4.2.9** - Web framework
- **Django REST Framework 3.14.0** - RESTful API
- **django-filter 23.5** - Advanced filtering for querysets
- **Pillow** - Image handling for documents and media
- **SQLite** - Database (development)
- **Python 3.x** - Programming language

### Frontend
- **PatternFly 5.3.1** - Enterprise UI framework
- **Alpine.js 3.x** - Lightweight reactive framework (3KB)
- **PatternFly Fonts** - Custom typography

## Project Structure

```
simple-aircraft-manager/
├── simple_aircraft_manager/     # Main project configuration
│   ├── settings.py              # Django settings
│   ├── urls.py                  # URL routing
│   ├── wsgi.py                  # WSGI entry point
│   └── asgi.py                  # ASGI entry point
├── core/                        # Core aircraft management
│   ├── models.py                # Aircraft, AircraftNote, AircraftEvent
│   ├── views.py                 # API ViewSets
│   ├── serializers.py           # DRF serializers
│   ├── admin.py                 # Admin configuration
│   ├── templates/               # Web templates
│   └── migrations/              # Database migrations
├── health/                      # Maintenance & compliance
│   ├── models.py                # 10 maintenance-related models
│   ├── views.py                 # API ViewSets
│   ├── serializers.py           # DRF serializers
│   ├── admin.py                 # Admin configuration
│   └── migrations/              # Database migrations
├── test-media/                  # Media file storage
│   ├── aircraft_pictures/       # Aircraft photos
│   └── health/documents/        # Maintenance documents
├── manage.py                    # Django management CLI
└── requirements.txt             # Python dependencies
```

## Features

### Core Features

- **Fleet Management**
  - Track aircraft by tail number, make, model, and serial number
  - Monitor aircraft status (Available, Maintenance, Grounded, Unavailable)
  - Record flight hours and operational history
  - Attach photos to aircraft records
  - Timestamped event logging for audit trails

- **Notes & Documentation**
  - Add operational notes to aircraft
  - Track note authors and timestamps
  - Edit history preservation

### Maintenance & Health Tracking

- **Component Management**
  - Hierarchical component tracking (components can have parent components)
  - Track TBO (Time Between Overhaul) intervals
  - Monitor service hours and inspection schedules
  - Component status tracking (Serviceable, Unserviceable, etc.)
  - Consumable vs. non-consumable classification

- **Squawk Tracking**
  - Log maintenance defects and issues
  - Priority levels: Ground Aircraft, Fix Soon, Fix at Next Inspection, Fix Eventually
  - Link squawks to specific components
  - Attach photos and documentation

- **Logbook Entries**
  - Digital logbook for Engine, Aircraft, Propeller entries
  - Track maintenance actions and flight hours
  - Associate entries with components

- **Inspections**
  - Define recurring inspection types
  - Schedule inspections based on hours or days
  - Record inspection completion
  - Track due dates and compliance

- **Regulatory Compliance**
  - Airworthiness Directive (AD) tracking
  - AD compliance recording with next due dates
  - Supplemental Type Certificate (STC) applications
  - Permanent and recurring compliance management

- **Document Management**
  - Organize documents in collections
  - Document types: Logbooks, Alterations, Reports, Estimates, Discrepancies, Invoices, Aircraft Documents, Other
  - Multi-page document support with image uploads
  - Link documents to aircraft

## Database Models

### Core App

- **Aircraft** - Central fleet inventory (UUID primary key)
  - tail_number, make, model, serial_number
  - status, flight_time, purchased date
  - picture upload support

- **AircraftNote** - Notes attached to aircraft
  - Links to Aircraft and User
  - Timestamps for creation and edits

- **AircraftEvent** - Audit trail of aircraft events
  - Timestamped events with categories

### Health App

- **ComponentType** - Component categories
- **Component** - Individual parts/components with maintenance tracking
- **DocumentCollection** - Logical document groupings
- **Document** - Maintenance documentation
- **DocumentImage** - Individual pages/images within documents
- **LogbookEntry** - Flight and maintenance logs
- **Squawk** - Maintenance defects
- **InspectionType** - Inspection requirements
- **InspectionRecord** - Inspection completion records
- **AD** - Airworthiness Directives
- **ADCompliance** - AD compliance tracking
- **STCApplication** - STC tracking

## API Endpoints

All API endpoints require authentication and are accessible at `/api/`.

### Core Endpoints

- `GET/POST /api/aircraft/` - List/create aircraft
- `GET/PUT/PATCH/DELETE /api/aircraft/{id}/` - Aircraft detail operations
- `GET/POST /api/aircraft-notes/` - Aircraft notes
- `GET /api/aircraft-events/` - Aircraft events (read-only audit log)
- `GET /api/users/` - User list (read-only)

### Health Management Endpoints

- `/api/component-type/` - Component types
- `/api/component/` - Component inventory
- `/api/document-collection/` - Document collections
- `/api/document/` - Documents
- `/api/document-image/` - Document images
- `/api/logbook/` - Logbook entries
- `/api/squawk/` - Maintenance squawks
- `/api/inspection-type/` - Inspection type definitions
- `/api/inspection/` - Inspection records
- `/api/ad/` - Airworthiness Directives
- `/api/ad-compliance/` - AD compliance records
- `/api/stc/` - STC applications

### Web Interface

- `/dashboard/` - Main dashboard
- `/admin/` - Django admin interface
- `/accounts/` - Authentication (login, logout, password reset)

## Installation

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

## Development Notes

### Current Configuration

- **DEBUG Mode**: Enabled (development)
- **Database**: SQLite (db.sqlite3)
- **Media Storage**: test-media/ directory
- **Authentication**: Required for all API endpoints
- **Admin Interface**: Enabled at /admin/

### Security Considerations

This is currently configured for development. Before deploying to production:

- [ ] Set `DEBUG = False` in settings.py
- [ ] Update `SECRET_KEY` to a secure random value
- [ ] Configure `ALLOWED_HOSTS` appropriately
- [ ] Use a production database (PostgreSQL, MySQL)
- [ ] Configure HTTPS/SSL
- [ ] Set up proper media file storage
- [ ] Review and update security middleware
- [ ] Configure proper logging

### Data Model Relationships

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
├── InspectionRecord (1:N)
└── AD/STC (M:N via compliance tables)
```

## Use Cases

This application supports:

1. **Fleet Operators** - Track multiple aircraft, status, and availability
2. **Maintenance Teams** - Log repairs, inspections, and component changes
3. **Quality Assurance** - Ensure compliance with ADs and inspection requirements
4. **Records Management** - Organize and maintain aircraft logbooks and documentation
5. **Component Tracking** - Monitor component lifecycles and TBO intervals

## Contributing

When contributing to this project:

1. Review the existing code structure and follow Django best practices
2. Run migrations after model changes: `python manage.py makemigrations`
3. Update API serializers when modifying models
4. Register new models in admin.py for admin interface access
5. Follow the UUID primary key pattern for new models

## License

[Add license information here]

## Contact

[Add contact information here]
