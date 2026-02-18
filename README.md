# Simple Aircraft Manager

> **Note**: This codebase was generated with [Claude](https://claude.ai), Anthropic's AI assistant, using [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

## Overview

Simple Aircraft Manager is an open-source, self-hosted solution for managing records and status for small fleets of aircraft. The goal of Simple Aircraft Manager is to create a streamlined experience to track aircraft records and status for individual owners and small-medium sized flying clubs with an emphasis on making it easy to share information with outsiders (mechanics, prospective buyers, etc).

## Features

- **Aircraft & Fleet Management** — Track multiple aircraft with images, flight hours, and status
- **Component Tracking** — Monitor component lifecycles, TBO limits, and service intervals
- **Airworthiness Status** — Automatic color-coded status based on ADs, squawks, inspections, and component health
- **Squawk Management** — Track maintenance issues with priority levels; ground aircraft as needed
- **Airworthiness Directives (ADs)** — Track AD compliance with recurring due dates and overdue detection
- **Inspection Tracking** — Manage periodic inspection requirements and compliance records
- **Logbook** — Maintenance log entries with AI-assisted transcription from scanned pages
- **Documents** — Organized document collections with multi-page viewer
- **Major Records** — Track major repairs and alterations
- **Oil & Fuel Tracking** — Consumption records with trend charts
- **Public Sharing** — Share read-only views with mechanics or prospective buyers without requiring an account
- **Role-Based Access** — Owner and pilot roles with per-aircraft permissions
- **OIDC Authentication** — Optional single sign-on via Keycloak or other OIDC providers

## Local Development

1. **Set up the environment**
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Initialize the database**
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```

3. **Run the development server**
   ```bash
   python manage.py runserver
   ```

4. **Access the application**
   - Dashboard: http://localhost:8000/dashboard/
   - Admin: http://localhost:8000/admin/
   - API: http://localhost:8000/api/

## Production Deployment

See [examples/openshift/](examples/openshift/) for a complete OpenShift/Kubernetes deployment example including PostgreSQL (Crunchy PGO), nginx TLS termination, OIDC authentication, and persistent media storage.

## Documentation

- [Features](docs/features.md) — Detailed feature documentation
- [Configuration](docs/configuration.md) — Environment variables and settings
- [API Reference](docs/api-reference.md) — REST API endpoints
- [Data Model](docs/data-model.md) — Database models and relationships
- [Architecture](docs/architecture.md) — Tech stack, project structure, and contributing guide

## License

This project is dedicated to the public domain. You may use, copy, modify, and distribute it for any purpose without restriction. See [The Unlicense](https://unlicense.org) for details.
