"""
Health-domain @action methods for AircraftViewSet.

All action methods are moved here verbatim from core/views.py.
They reference self.get_object(), self.request, etc. — works via MRO.
"""
import logging
import re
from datetime import date as date_cls
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.apps import apps
from django.conf import settings as django_settings
from django.db import transaction
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from core.action_registry import (
    register_owner_actions,
    register_pilot_actions,
    register_read_pilot_write_owner,
)
from core.events import log_event
from core.features import feature_available, get_feature_catalog, get_known_feature_names
from core.models import AircraftEvent
from core.serializers import (
    AircraftNoteNestedSerializer,
    AircraftNoteCreateUpdateSerializer,
    AircraftEventNestedSerializer,
    AircraftSerializer,
)
from health.dispatch import dispatch_import
from health.models import (
    Component, ImportJob, LogbookEntry, Squawk, Document, DocumentCollection,
    ConsumableRecord, AD, ADCompliance, InspectionType, InspectionRecord,
    MajorRepairAlteration, OilAnalysisReport, FlightLog,
)
from health.serializers import (
    ComponentSerializer, ComponentCreateUpdateSerializer,
    LogbookEntrySerializer, SquawkSerializer,
    SquawkNestedSerializer, SquawkCreateUpdateSerializer,
    DocumentCollectionNestedSerializer, DocumentNestedSerializer,
    ConsumableRecordNestedSerializer, ConsumableRecordCreateSerializer,
    ADNestedSerializer, ADComplianceNestedSerializer,
    ADSerializer,
    InspectionTypeSerializer, InspectionTypeNestedSerializer,
    InspectionRecordNestedSerializer,
    MajorRepairAlterationNestedSerializer,
    OilAnalysisReportSerializer, OilAnalysisReportCreateUpdateSerializer,
    FlightLogNestedSerializer, FlightLogCreateUpdateSerializer,
)
from health.oil_analysis_import import run_oil_analysis_job
from health.services import (
    end_of_month_after, ad_compliance_status, inspection_compliance_status,
    STATUS_LABELS,
)

# Register permissions at module load time.
register_owner_actions('components', 'remove_ad', 'compliance', 'remove_inspection_type')
register_pilot_actions('update_hours', 'squawks', 'notes', 'oil_records', 'fuel_records',
                       'flight_logs', 'summary', 'documents', 'events')
register_read_pilot_write_owner('ads', 'inspections', 'major_records',
                                'oil_analysis', 'oil_analysis_ai_extract',
                                'features')

logger = logging.getLogger(__name__)


class HealthAircraftActionsMixin:
    """Health-domain @action methods for AircraftViewSet."""

    @action(detail=True, methods=['post'])
    def update_hours(self, request, pk=None):
        """
        Update aircraft tach/hobbs hours and automatically sync to all in-service components.
        POST /api/aircraft/{id}/update_hours/

        Body: {
            "new_tach_time": 1234.5,   # primary (cumulative total)
            "new_hours": 1234.5,        # backward-compat alias for new_tach_time
            "new_hobbs_time": 1240.0,  # optional
        }
        """
        aircraft = self.get_object()

        # Support both new_tach_time and backward-compat new_hours
        new_tach_raw = request.data.get('new_tach_time') or request.data.get('new_hours')

        if new_tach_raw is None:
            return Response({'error': 'new_tach_time required'},
                          status=status.HTTP_400_BAD_REQUEST)

        try:
            new_tach_time = Decimal(str(new_tach_raw))
        except (ValueError, InvalidOperation, TypeError):
            return Response({'error': 'Invalid tach time value'},
                          status=status.HTTP_400_BAD_REQUEST)

        hours_delta = new_tach_time - aircraft.tach_time
        old_tach = aircraft.tach_time

        # Update aircraft tach
        aircraft.tach_time = new_tach_time

        # Optional hobbs update
        new_hobbs_raw = request.data.get('new_hobbs_time')
        if new_hobbs_raw is not None:
            try:
                new_hobbs_time = Decimal(str(new_hobbs_raw))
                aircraft.hobbs_time = new_hobbs_time
            except (ValueError, InvalidOperation, TypeError):
                return Response({'error': 'Invalid hobbs time value'},
                              status=status.HTTP_400_BAD_REQUEST)

        aircraft.save()

        # ALWAYS update all in-service components (not optional)
        # Clamp component hours at 0 to prevent negative values on corrections.
        components = aircraft.components.filter(status='IN-USE')
        updated_components = []
        for component in components:
            component.hours_in_service = max(Decimal('0'), component.hours_in_service + hours_delta)
            component.hours_since_overhaul = max(Decimal('0'), component.hours_since_overhaul + hours_delta)
            component.save()
            updated_components.append(str(component.id))

        delta_sign = '+' if hours_delta >= 0 else ''
        log_event(
            aircraft, 'hours',
            f"Hours {'updated' if hours_delta >= 0 else 'corrected'} to {new_tach_time}",
            user=request.user,
            notes=f"Previous: {old_tach}, delta: {delta_sign}{hours_delta}",
        )

        return Response({
            'success': True,
            'aircraft_hours': float(aircraft.tach_time),  # backward compat
            'tach_time': float(aircraft.tach_time),
            'hobbs_time': float(aircraft.hobbs_time),
            'hours_added': float(hours_delta),
            'components_updated': len(updated_components),
        })

    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        """
        Get aircraft summary with components, recent logs, active squawks, notes
        GET /api/aircraft/{id}/summary/
        """
        aircraft = self.get_object()

        return Response({
            'aircraft': AircraftSerializer(aircraft, context={'request': request}).data,
            'components': ComponentSerializer(
                aircraft.components.all(),
                many=True,
                context={'request': request}
            ).data,
            'recent_logs': LogbookEntrySerializer(
                aircraft.logbook_entries.order_by('-date')[:10],
                many=True,
                context={'request': request}
            ).data,
            'active_squawks': SquawkNestedSerializer(
                aircraft.squawks.filter(resolved=False),
                many=True,
                context={'request': request}
            ).data,
            'notes': AircraftNoteNestedSerializer(
                aircraft.notes.order_by('-added_timestamp'),
                many=True,
                context={'request': request}
            ).data,
            'features': {f: feature_available(f, aircraft) for f in get_known_feature_names()},
            'feature_catalog': get_feature_catalog(),
        })

    @action(detail=True, methods=['get'])
    def documents(self, request, pk=None):
        """
        Get aircraft documents organized by collection
        GET /api/aircraft/{id}/documents/

        Returns:
        - collections: List of document collections with their documents
        - uncollected_documents: Documents not in any collection
        """
        aircraft = self.get_object()

        # Get all collections for this aircraft with their documents
        collections = aircraft.doc_collections.prefetch_related('documents__images').all()

        # Get documents not in any collection
        uncollected_documents = aircraft.documents.filter(
            collection__isnull=True
        ).prefetch_related('images')

        return Response({
            'collections': DocumentCollectionNestedSerializer(
                collections,
                many=True,
                context={'request': request}
            ).data,
            'uncollected_documents': DocumentNestedSerializer(
                uncollected_documents,
                many=True,
                context={'request': request}
            ).data,
        })

    @action(detail=True, methods=['get', 'post'])
    def squawks(self, request, pk=None):
        """
        Get or create squawks for an aircraft
        GET /api/aircraft/{id}/squawks/ - Get all squawks (active and resolved)
        POST /api/aircraft/{id}/squawks/ - Create a new squawk

        Query params for GET:
        - resolved: true/false (filter by resolved status)
        """
        aircraft = self.get_object()

        if request.method == 'GET':
            squawks = aircraft.squawks.all().order_by('-created_at')

            # Filter by resolved status if specified
            resolved_param = request.query_params.get('resolved')
            if resolved_param is not None:
                resolved = resolved_param.lower() == 'true'
                squawks = squawks.filter(resolved=resolved)

            return Response({
                'squawks': SquawkNestedSerializer(
                    squawks,
                    many=True,
                    context={'request': request}
                ).data,
            })

        elif request.method == 'POST':
            # Create a new squawk for this aircraft
            data = request.data.copy()
            data['aircraft'] = aircraft.id

            # Set reported_by to current user if authenticated
            if request.user.is_authenticated:
                data['reported_by'] = request.user.id

            serializer = SquawkCreateUpdateSerializer(data=data)
            if serializer.is_valid():
                squawk = serializer.save()
                log_event(
                    aircraft, 'squawk',
                    f"Squawk reported: {squawk.get_priority_display()}",
                    user=request.user,
                )
                return Response(
                    SquawkNestedSerializer(squawk, context={'request': request}).data,
                    status=status.HTTP_201_CREATED
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get', 'post'])
    def notes(self, request, pk=None):
        """
        Get or create notes for an aircraft
        GET /api/aircraft/{id}/notes/ - Get all notes
        POST /api/aircraft/{id}/notes/ - Create a new note
        """
        aircraft = self.get_object()

        if request.method == 'GET':
            notes = aircraft.notes.all().order_by('-added_timestamp')

            return Response({
                'notes': AircraftNoteNestedSerializer(
                    notes,
                    many=True,
                    context={'request': request}
                ).data,
            })

        elif request.method == 'POST':
            # Create a new note for this aircraft
            data = request.data.copy()
            data['aircraft'] = aircraft.id

            serializer = AircraftNoteCreateUpdateSerializer(data=data)
            if serializer.is_valid():
                # Set added_by to current user if authenticated
                note = serializer.save(
                    added_by=request.user if request.user.is_authenticated else None
                )
                log_event(aircraft, 'note', "Note added", user=request.user)
                return Response(
                    AircraftNoteNestedSerializer(note, context={'request': request}).data,
                    status=status.HTTP_201_CREATED
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def _consumable_records_action(self, request, aircraft, record_type):
        """Shared handler for oil_records and fuel_records actions."""
        response_key = f"{record_type}_records"
        log_category = record_type
        unit = 'qt' if record_type == ConsumableRecord.RECORD_TYPE_OIL else 'gal'

        if request.method == 'GET':
            records = aircraft.consumable_records.filter(record_type=record_type)
            return Response({
                response_key: ConsumableRecordNestedSerializer(records, many=True).data,
            })

        data = request.data.copy()
        data['aircraft'] = aircraft.id
        data['record_type'] = record_type
        if 'flight_hours' not in data or not data['flight_hours']:
            data['flight_hours'] = str(aircraft.tach_time)

        serializer = ConsumableRecordCreateSerializer(data=data)
        if serializer.is_valid():
            record = serializer.save()
            log_event(
                aircraft, log_category,
                f"{record_type.capitalize()} added: {record.quantity_added} {unit}",
                user=request.user,
            )
            return Response(
                ConsumableRecordNestedSerializer(record).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get', 'post'])
    def oil_records(self, request, pk=None):
        """
        Get or create oil records for an aircraft
        GET /api/aircraft/{id}/oil_records/ - Get all oil records
        POST /api/aircraft/{id}/oil_records/ - Create a new oil record
        """
        return self._consumable_records_action(request, self.get_object(), ConsumableRecord.RECORD_TYPE_OIL)

    @action(detail=True, methods=['get', 'post'])
    def fuel_records(self, request, pk=None):
        """
        Get or create fuel records for an aircraft
        GET /api/aircraft/{id}/fuel_records/ - Get all fuel records
        POST /api/aircraft/{id}/fuel_records/ - Create a new fuel record
        """
        return self._consumable_records_action(request, self.get_object(), ConsumableRecord.RECORD_TYPE_FUEL)

    @action(detail=True, methods=['post'])
    def components(self, request, pk=None):
        """
        Create a component for an aircraft
        POST /api/aircraft/{id}/components/
        """
        aircraft = self.get_object()

        data = request.data.copy()
        data['aircraft'] = aircraft.id

        serializer = ComponentCreateUpdateSerializer(data=data)
        if serializer.is_valid():
            component = serializer.save(aircraft=aircraft)
            log_event(
                aircraft, 'component',
                f"Component added: {component.component_type.name}",
                user=request.user,
            )
            return Response(
                ComponentSerializer(component, context={'request': request}).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get', 'post'])
    def ads(self, request, pk=None):
        """
        Get applicable ADs with compliance status, or add an AD to this aircraft.
        GET /api/aircraft/{id}/ads/ - Get all applicable ADs with compliance info
        POST /api/aircraft/{id}/ads/ - Add existing AD (ad_id) or create new AD
        """
        aircraft = self.get_object()

        if request.method == 'GET':
            # Get ADs applicable to this aircraft (direct or via components)
            component_ids = aircraft.components.values_list('id', flat=True)
            aircraft_ads = AD.objects.filter(applicable_aircraft=aircraft)
            component_ads = AD.objects.filter(applicable_component__in=component_ids)
            all_ads = (aircraft_ads | component_ads).distinct()

            current_hours = aircraft.tach_time - aircraft.tach_time_offset

            ads_data = []
            for ad in all_ads:
                ad_dict = ADNestedSerializer(ad).data

                # Get latest compliance record
                compliance = ADCompliance.objects.filter(
                    ad=ad
                ).filter(
                    Q(aircraft=aircraft) | Q(component__aircraft=aircraft)
                ).order_by('-date_complied').first()

                if compliance:
                    ad_dict['latest_compliance'] = ADComplianceNestedSerializer(compliance).data
                else:
                    ad_dict['latest_compliance'] = None

                # Conditional ADs use a separate status that doesn't affect airworthiness
                if ad.compliance_type == 'conditional':
                    ad_dict['compliance_status'] = 'compliant' if compliance else 'conditional'
                    ads_data.append(ad_dict)
                    continue

                if not compliance:
                    ad_dict['compliance_status'] = 'no_compliance'
                elif compliance.permanent:
                    ad_dict['compliance_status'] = 'compliant'
                else:
                    today = date_cls.today()
                    rank, extras = ad_compliance_status(ad, compliance, current_hours, today)
                    ad_dict.update(extras)
                    ad_dict['compliance_status'] = STATUS_LABELS[rank]

                ads_data.append(ad_dict)

            return Response({'ads': ads_data})

        elif request.method == 'POST':
            ad_id = request.data.get('ad_id')
            if ad_id:
                # Add existing AD to this aircraft
                try:
                    ad = AD.objects.get(id=ad_id)
                except (AD.DoesNotExist, ValueError):
                    return Response({'error': 'AD not found'}, status=status.HTTP_404_NOT_FOUND)
                ad.applicable_aircraft.add(aircraft)
                log_event(aircraft, 'ad', f"AD linked: {ad.name}", user=request.user)
                return Response(ADNestedSerializer(ad).data, status=status.HTTP_200_OK)
            else:
                # Create a new AD and add to this aircraft
                serializer = ADSerializer(data=request.data, context={'request': request})
                if serializer.is_valid():
                    ad = serializer.save()
                    ad.applicable_aircraft.add(aircraft)
                    log_event(aircraft, 'ad', f"AD created: {ad.name}", user=request.user)
                    return Response(ADNestedSerializer(ad).data, status=status.HTTP_201_CREATED)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='remove_ad')
    def remove_ad(self, request, pk=None):
        """
        Remove an AD from this aircraft's applicable_aircraft M2M.
        POST /api/aircraft/{id}/remove_ad/
        Body: {"ad_id": "<uuid>"}
        """
        aircraft = self.get_object()
        ad_id = request.data.get('ad_id')
        if not ad_id:
            return Response({'error': 'ad_id required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            ad = AD.objects.get(id=ad_id)
        except (AD.DoesNotExist, ValueError):
            return Response({'error': 'AD not found'}, status=status.HTTP_404_NOT_FOUND)

        ad.applicable_aircraft.remove(aircraft)
        return Response({'success': True})

    @action(detail=True, methods=['post'])
    def compliance(self, request, pk=None):
        """
        Create an AD compliance record for this aircraft.
        POST /api/aircraft/{id}/compliance/
        """
        aircraft = self.get_object()
        data = request.data.copy()
        data['aircraft'] = aircraft.id

        serializer = ADComplianceNestedSerializer(data=data)
        if serializer.is_valid():
            record = serializer.save()
            ad_name = record.ad.name if record.ad else "Unknown"
            log_event(
                aircraft, 'ad',
                f"AD compliance recorded: {ad_name}",
                user=request.user,
            )
            return Response(
                ADComplianceNestedSerializer(record).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get', 'post'])
    def inspections(self, request, pk=None):
        """
        Get applicable InspectionTypes with status, or create a new InspectionRecord.
        GET /api/aircraft/{id}/inspections/ - Get all applicable inspection types with last record and status
        POST /api/aircraft/{id}/inspections/ - Create a new InspectionRecord for the aircraft
        """
        aircraft = self.get_object()

        if request.method == 'GET':
            component_ids = aircraft.components.values_list('id', flat=True)
            aircraft_inspections = InspectionType.objects.filter(applicable_aircraft=aircraft)
            component_inspections = InspectionType.objects.filter(applicable_component__in=component_ids)
            all_types = (aircraft_inspections | component_inspections).distinct()

            current_hours = aircraft.tach_time - aircraft.tach_time_offset
            today = date_cls.today()

            result = []
            for insp_type in all_types:
                type_dict = InspectionTypeNestedSerializer(insp_type).data

                last_record = InspectionRecord.objects.filter(
                    inspection_type=insp_type
                ).filter(
                    Q(aircraft=aircraft) | Q(component__aircraft=aircraft)
                ).order_by('-date').first()

                if last_record:
                    type_dict['latest_record'] = InspectionRecordNestedSerializer(last_record).data
                else:
                    type_dict['latest_record'] = None

                if not last_record:
                    type_dict['compliance_status'] = 'never_completed'
                else:
                    rank, extras = inspection_compliance_status(insp_type, last_record, current_hours, today)
                    type_dict.update(extras)
                    type_dict['compliance_status'] = STATUS_LABELS[rank]

                result.append(type_dict)

            return Response({'inspection_types': result})

        elif request.method == 'POST':
            # Case 1: Add existing InspectionType to aircraft
            type_id = request.data.get('inspection_type_id')
            if type_id:
                try:
                    insp_type = InspectionType.objects.get(id=type_id)
                except (InspectionType.DoesNotExist, ValueError):
                    return Response({'error': 'InspectionType not found'}, status=status.HTTP_404_NOT_FOUND)
                insp_type.applicable_aircraft.add(aircraft)
                log_event(aircraft, 'inspection', f"Inspection type linked: {insp_type.name}", user=request.user)
                return Response(InspectionTypeNestedSerializer(insp_type).data, status=status.HTTP_200_OK)

            # Case 2: Create new InspectionType and add to aircraft
            if request.data.get('create_type'):
                create_data = {k: v for k, v in request.data.items() if k != 'create_type'}
                serializer = InspectionTypeSerializer(data=create_data, context={'request': request})
                if serializer.is_valid():
                    insp_type = serializer.save()
                    insp_type.applicable_aircraft.add(aircraft)
                    log_event(aircraft, 'inspection', f"Inspection type created: {insp_type.name}", user=request.user)
                    return Response(InspectionTypeNestedSerializer(insp_type).data, status=status.HTTP_201_CREATED)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            # Case 3: Create a new InspectionRecord for the aircraft
            data = request.data.copy()
            data['aircraft'] = aircraft.id

            serializer = InspectionRecordNestedSerializer(data=data)
            if serializer.is_valid():
                record = serializer.save()
                type_name = record.inspection_type.name if record.inspection_type else "Unknown"
                log_event(
                    aircraft, 'inspection',
                    f"Inspection completed: {type_name}",
                    user=request.user,
                )
                return Response(
                    InspectionRecordNestedSerializer(record).data,
                    status=status.HTTP_201_CREATED
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get', 'post'], url_path='major_records')
    def major_records(self, request, pk=None):
        """
        Get or create major repair/alteration records for an aircraft.
        GET  /api/aircraft/{id}/major_records/
        POST /api/aircraft/{id}/major_records/
        """
        aircraft = self.get_object()

        if request.method == 'GET':
            records = MajorRepairAlteration.objects.filter(aircraft=aircraft)
            serializer = MajorRepairAlterationNestedSerializer(records, many=True)
            return Response(serializer.data)

        data = request.data.copy()
        data['aircraft'] = aircraft.id
        serializer = MajorRepairAlterationNestedSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        record = serializer.save()
        log_event(aircraft, 'major_record',
                  f'{record.get_record_type_display()} created: {record.title}',
                  user=request.user)
        return Response(
            MajorRepairAlterationNestedSerializer(record).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['get', 'post'], url_path='flight_logs')
    def flight_logs(self, request, pk=None):
        """
        Get or create flight log entries for an aircraft.
        GET  /api/aircraft/{id}/flight_logs/
        POST /api/aircraft/{id}/flight_logs/
        """
        aircraft = self.get_object()

        if request.method == 'GET':
            logs = aircraft.flight_logs.all()
            return Response({
                'flight_logs': FlightLogNestedSerializer(logs, many=True).data,
            })

        # POST — create a new flight log
        data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
        data['aircraft'] = str(aircraft.id)

        serializer = FlightLogCreateUpdateSerializer(data=data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            flight = serializer.save()
            tach_delta = flight.tach_time
            aircraft.tach_time += tach_delta
            if flight.hobbs_time:
                aircraft.hobbs_time += flight.hobbs_time
            aircraft.save()

            # Sync IN-USE component hours
            for comp in aircraft.components.filter(status='IN-USE'):
                comp.hours_in_service += tach_delta
                comp.hours_since_overhaul += tach_delta
                comp.save()

            # Auto-create ConsumableRecords for oil/fuel added
            if flight.oil_added:
                ConsumableRecord.objects.create(
                    record_type=ConsumableRecord.RECORD_TYPE_OIL,
                    aircraft=aircraft,
                    date=flight.date,
                    quantity_added=flight.oil_added,
                    level_after=flight.oil_level_after,
                    consumable_type=flight.oil_added_type or '',
                    flight_hours=aircraft.tach_time,
                    notes=f"Auto-created from flight log {flight.id}",
                )
            if flight.fuel_added:
                ConsumableRecord.objects.create(
                    record_type=ConsumableRecord.RECORD_TYPE_FUEL,
                    aircraft=aircraft,
                    date=flight.date,
                    quantity_added=flight.fuel_added,
                    level_after=flight.fuel_level_after,
                    consumable_type=flight.fuel_added_type or '',
                    flight_hours=aircraft.tach_time,
                    notes=f"Auto-created from flight log {flight.id}",
                )

            route_str = ''
            if flight.departure_location and flight.destination_location:
                route_str = f" ({flight.departure_location}→{flight.destination_location})"
            log_event(
                aircraft, 'flight',
                f"Flight logged: {flight.tach_time} hrs{route_str}",
                user=request.user,
            )

        return Response(
            FlightLogNestedSerializer(flight).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['get', 'post'])
    def features(self, request, pk=None):
        """
        Get or update feature flags for an aircraft.
        GET  /api/aircraft/{id}/features/
        POST /api/aircraft/{id}/features/  — owner only
        Body: {"feature": "<name>", "enabled": true|false}
        """
        from core.models import AircraftFeature

        aircraft = self.get_object()

        catalog = get_feature_catalog()
        known_names = [f['name'] for f in catalog]

        if request.method == 'GET':
            return Response({
                'features': {f: feature_available(f, aircraft) for f in known_names},
                'feature_catalog': catalog,
            })

        # POST — owner only (enforced by registry)
        feature_name = request.data.get('feature')
        enabled = request.data.get('enabled')

        if feature_name not in known_names:
            return Response(
                {'error': f'Unknown feature. Valid features: {known_names}'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not isinstance(enabled, bool):
            return Response(
                {'error': 'enabled must be a boolean'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if feature_name in getattr(django_settings, 'DISABLED_FEATURES', []) and enabled:
            return Response(
                {'error': f'{feature_name!r} is disabled globally and cannot be enabled here'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        AircraftFeature.objects.update_or_create(
            aircraft=aircraft,
            feature=feature_name,
            defaults={'enabled': enabled, 'updated_by': request.user},
        )
        log_event(
            aircraft, 'aircraft',
            f"Feature {'enabled' if enabled else 'disabled'}: {feature_name}",
            user=request.user,
        )
        return Response({
            'features': {f: feature_available(f, aircraft) for f in known_names},
            'feature_catalog': catalog,
        })

    @action(detail=True, methods=['get'])
    def events(self, request, pk=None):
        """
        Get events/activity log for an aircraft.
        GET /api/aircraft/{id}/events/?limit=50&category=hours
        """
        aircraft = self.get_object()
        qs = AircraftEvent.objects.filter(aircraft=aircraft).select_related('user')

        category = request.query_params.get('category')
        if category:
            from core.models import EVENT_CATEGORIES
            valid_categories = {c[0] for c in EVENT_CATEGORIES}
            if category not in valid_categories:
                return Response({'error': f"Invalid category '{category}'."}, status=status.HTTP_400_BAD_REQUEST)
            qs = qs.filter(category=category)

        total = qs.count()

        try:
            limit = min(int(request.query_params.get('limit', 50)), 200)
        except (ValueError, TypeError):
            limit = 50

        events = qs[:limit]
        return Response({
            'events': AircraftEventNestedSerializer(events, many=True).data,
            'total': total,
        })

    @action(detail=True, methods=['get', 'post'], url_path='oil_analysis')
    def oil_analysis(self, request, pk=None):
        """
        Get or create oil analysis reports for an aircraft.
        GET  /api/aircraft/{id}/oil_analysis/
        POST /api/aircraft/{id}/oil_analysis/
        """
        aircraft = self.get_object()

        if request.method == 'GET':
            reports = OilAnalysisReport.objects.filter(aircraft=aircraft).select_related('component__component_type')
            component_filter = request.query_params.get('component')
            if component_filter:
                reports = reports.filter(component_id=component_filter)

            # Return engine components for the filter dropdown
            engine_components = Component.objects.filter(
                aircraft=aircraft,
                status='IN-USE',
                tbo_critical=True,
            ).select_related('component_type')

            return Response({
                'oil_analysis_reports': OilAnalysisReportSerializer(reports, many=True).data,
                'components': ComponentSerializer(engine_components, many=True, context={'request': request}).data,
            })

        data = request.data.copy()
        data['aircraft'] = str(aircraft.id)
        serializer = OilAnalysisReportCreateUpdateSerializer(data=data)
        if serializer.is_valid():
            report = serializer.save()
            log_event(aircraft, 'oil', 'Oil analysis report added', user=request.user)
            return Response(
                OilAnalysisReportSerializer(report).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='oil_analysis_ai_extract')
    def oil_analysis_ai_extract(self, request, pk=None):
        """
        Start an async oil analysis AI extraction job. Does NOT save to DB.
        POST /api/aircraft/{id}/oil_analysis_ai_extract/
        Multipart fields: file (PDF), model, provider
        Returns 202 immediately with {job_id}. Poll /api/aircraft/import/{job_id}/ for status.
        """
        aircraft = self.get_object()  # checks permission/ownership

        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response({'error': 'file is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate file type and enforce a tighter size limit for the synchronous PDF parser
        from health.serializers import validate_uploaded_file
        OIL_ANALYSIS_MAX_PDF_SIZE = 50 * 1024 * 1024  # 50 MB
        if uploaded_file.size > OIL_ANALYSIS_MAX_PDF_SIZE:
            return Response(
                {'error': 'PDF file size exceeds the 50 MB limit for oil analysis.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from rest_framework.exceptions import ValidationError
        try:
            validate_uploaded_file(uploaded_file)
        except ValidationError as exc:
            # Serializer/Validation errors are safe to show the user
            return Response({'error': exc.detail if hasattr(exc, 'detail') else str(exc)}, 
                            status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            # Unexpected system errors should not leak details
            logger.exception("Unexpected error during file validation")
            return Response({'error': 'An internal error occurred during file validation.'}, 
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        job = ImportJob(
            aircraft=aircraft,
            user=request.user,
            job_type='oil_analysis',
        )

        # Stage on shared storage when Procrastinate workers run in separate pods.
        suffix = Path(uploaded_file.name).suffix.lower() if uploaded_file.name else '.pdf'
        staging_root = getattr(
            django_settings,
            'IMPORT_STAGING_DIR',
            Path(django_settings.BASE_DIR) / 'import_staging',
        )
        staging_dir = Path(staging_root) / 'oil_analysis_jobs' / str(job.id)
        tmp_path = staging_dir / f"upload{suffix}"

        try:
            staging_dir.mkdir(parents=True, exist_ok=True)
            with tmp_path.open('wb') as tmp:
                for chunk in uploaded_file.chunks():
                    tmp.write(chunk)
        except OSError:
            logger.exception("Failed to stage oil analysis PDF")
            return Response(
                {'error': 'Failed to stage the PDF. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        job.save()

        task = None
        if apps.is_installed('procrastinate.contrib.django'):
            from health.tasks import import_oil_analysis_task
            task = import_oil_analysis_task

        dispatch_import(
            task,
            run_oil_analysis_job,
            (str(job.id), tmp_path),
            job_id=str(job.id),
            pdf_path=str(tmp_path),
        )

        return Response({'job_id': str(job.id)}, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=['post'], url_path='remove_inspection_type')
    def remove_inspection_type(self, request, pk=None):
        """
        Remove an InspectionType from this aircraft's applicable_aircraft M2M.
        POST /api/aircraft/{id}/remove_inspection_type/
        Body: {"inspection_type_id": "<uuid>"}
        """
        aircraft = self.get_object()
        type_id = request.data.get('inspection_type_id')
        if not type_id:
            return Response({'error': 'inspection_type_id required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            insp_type = InspectionType.objects.get(id=type_id)
        except (InspectionType.DoesNotExist, ValueError):
            return Response({'error': 'InspectionType not found'}, status=status.HTTP_404_NOT_FOUND)

        insp_type.applicable_aircraft.remove(aircraft)
        return Response({'success': True})
