import json
import logging
import os
import re
import shutil
import tarfile
import tempfile
import threading
import uuid
import zipfile
from datetime import date as date_cls, timedelta as td
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.db import transaction
from django.db.models import F
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views import View
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Prefetch
from rest_framework import viewsets, status
from rest_framework.permissions import IsAdminUser
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.events import log_event
from core.mixins import AircraftScopedMixin, EventLoggingMixin
from core.forms import RegistrationForm, UserProfileForm
from core.models import Aircraft, AircraftNote, AircraftEvent, AircraftRole, AircraftShareToken, InvitationCode, InvitationCodeAircraftRole, InvitationCodeRedemption
from core.permissions import (
    get_user_role, has_aircraft_permission, user_can_create_aircraft,
    CanCreateAircraft, IsAircraftOwnerOrAdmin, IsAircraftPilotOrAbove,
)
from core.serializers import (
    AircraftSerializer, AircraftListSerializer, AircraftNoteSerializer,
    AircraftNoteNestedSerializer, AircraftNoteCreateUpdateSerializer,
    AircraftEventSerializer, AircraftEventNestedSerializer,
    AircraftRoleSerializer, AircraftShareTokenSerializer,
    InvitationCodeSerializer, InvitationCodeDetailSerializer,
    InvitationCodeAircraftRoleSerializer,
)
from health.models import (
    Component, LogbookEntry, Squawk, Document, DocumentCollection,
    ConsumableRecord, AD, ADCompliance, InspectionType, InspectionRecord,
    MajorRepairAlteration, OilAnalysisReport,
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
)
from health.services import (
    end_of_month_after, ad_compliance_status, inspection_compliance_status,
    STATUS_LABELS,
)

logger = logging.getLogger(__name__)


User = get_user_model()


class AircraftViewSet(viewsets.ModelViewSet):
    queryset = Aircraft.objects.all()
    serializer_class = AircraftSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated(), CanCreateAircraft()]
        if self.action in ('update', 'partial_update', 'destroy',
                           'components', 'remove_ad', 'compliance',
                           'remove_inspection_type',
                           'manage_roles', 'manage_share_tokens', 'delete_share_token'):
            return [IsAuthenticated(), IsAircraftOwnerOrAdmin()]
        # ADs, inspections, and major records: GET is readable by pilots, POST/DELETE requires owner
        if self.action in ('ads', 'inspections', 'major_records'):
            if self.request.method == 'GET':
                return [IsAuthenticated(), IsAircraftPilotOrAbove()]
            return [IsAuthenticated(), IsAircraftOwnerOrAdmin()]
        # Oil analysis: GET readable by pilots, POST/AI-extract requires owner
        if self.action in ('oil_analysis', 'oil_analysis_ai_extract'):
            if self.request.method == 'GET':
                return [IsAuthenticated(), IsAircraftPilotOrAbove()]
            return [IsAuthenticated(), IsAircraftOwnerOrAdmin()]
        if self.action in ('update_hours', 'squawks', 'notes',
                           'oil_records', 'fuel_records'):
            return [IsAuthenticated(), IsAircraftPilotOrAbove()]
        # list, retrieve, summary, documents, events
        return [IsAuthenticated(), IsAircraftPilotOrAbove()]

    def get_queryset(self):
        qs = super().get_queryset().prefetch_related('roles')
        user = self.request.user
        if not user.is_authenticated:
            return qs.none()
        if user.is_staff or user.is_superuser:
            return qs
        accessible = AircraftRole.objects.filter(user=user).values_list('aircraft_id', flat=True)
        return qs.filter(id__in=accessible)

    def get_serializer_class(self):
        """Use lightweight serializer for list, full serializer for detail."""
        if self.action == 'list':
            return AircraftListSerializer
        return AircraftSerializer

    def perform_create(self, serializer):
        with transaction.atomic():
            aircraft = serializer.save()
            AircraftRole.objects.create(aircraft=aircraft, user=self.request.user, role='owner')
        log_event(aircraft, 'aircraft', 'Aircraft created', user=self.request.user)

    @action(detail=True, methods=['post'])
    def update_hours(self, request, pk=None):
        """
        Update aircraft hours and automatically sync to all in-service components
        POST /api/aircraft/{id}/update_hours/

        Body: {
            "new_hours": 1234.5
        }
        """
        aircraft = self.get_object()
        new_hours = request.data.get('new_hours')

        # Validation
        if new_hours is None:
            return Response({'error': 'new_hours required'},
                          status=status.HTTP_400_BAD_REQUEST)

        try:
            new_hours = Decimal(str(new_hours))
        except (ValueError, InvalidOperation, TypeError):
            return Response({'error': 'Invalid hours value'},
                          status=status.HTTP_400_BAD_REQUEST)

        if new_hours < aircraft.flight_time:
            return Response({'error': 'Hours cannot decrease'},
                          status=status.HTTP_400_BAD_REQUEST)

        hours_delta = new_hours - aircraft.flight_time
        old_hours = aircraft.flight_time

        # Update aircraft
        aircraft.flight_time = new_hours
        aircraft.save()

        # ALWAYS update all in-service components (not optional)
        components = aircraft.components.filter(status='IN-USE')
        updated_components = []
        for component in components:
            component.hours_in_service += hours_delta
            component.hours_since_overhaul += hours_delta
            component.save()
            updated_components.append(str(component.id))

        log_event(
            aircraft, 'hours',
            f"Hours updated to {new_hours}",
            user=request.user,
            notes=f"Previous: {old_hours}, delta: +{hours_delta}",
        )

        return Response({
            'success': True,
            'aircraft_hours': float(aircraft.flight_time),
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
            data['flight_hours'] = str(aircraft.flight_time)

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

            current_hours = aircraft.flight_time

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

            current_hours = aircraft.flight_time
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
        try:
            validate_uploaded_file(uploaded_file)
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        model = request.data.get('model', '')
        provider = request.data.get('provider', 'parser')

        # Write to a temp file; the job runner is responsible for cleanup
        import tempfile
        from pathlib import Path as _Path
        suffix = Path(uploaded_file.name).suffix.lower() if uploaded_file.name else '.pdf'
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            for chunk in uploaded_file.chunks():
                tmp.write(chunk)
            tmp_path = _Path(tmp.name)

        from health.models import ImportJob
        from health.oil_analysis_import import run_oil_analysis_job
        job = ImportJob.objects.create(
            aircraft=aircraft,
            user=request.user,
            job_type='oil_analysis',
        )

        t = threading.Thread(
            target=run_oil_analysis_job,
            args=(job.id, tmp_path),
            daemon=True,
        )
        t.start()

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

    @action(detail=True, methods=['get', 'post', 'delete'], url_path='manage_roles')
    def manage_roles(self, request, pk=None):
        """
        List, add/update, or remove role assignments.
        GET  - List all roles
        POST - Add or update a role: {user: <user_id>, role: 'owner'|'pilot'}
        DELETE - Remove a role: {user: <user_id>}
        """
        aircraft = self.get_object()

        if request.method == 'GET':
            roles = AircraftRole.objects.filter(aircraft=aircraft).select_related('user')
            return Response({
                'roles': AircraftRoleSerializer(roles, many=True).data,
            })

        if request.method == 'POST':
            user_id = request.data.get('user')
            role = request.data.get('role')
            if not user_id or role not in ('owner', 'pilot'):
                return Response({'error': 'Valid user and role required.'},
                                status=status.HTTP_400_BAD_REQUEST)
            try:
                target_user = User.objects.get(pk=user_id)
            except (User.DoesNotExist, ValueError):
                # Uniform error to prevent user enumeration
                return Response({'error': 'Valid user and role required.'},
                                status=status.HTTP_400_BAD_REQUEST)

            existing = AircraftRole.objects.filter(aircraft=aircraft, user=target_user).first()
            if existing:
                # Changing role
                if existing.role == 'owner' and role == 'pilot':
                    # Demoting owner — check last-owner protection
                    if not request.user.is_staff:
                        owner_count = AircraftRole.objects.filter(
                            aircraft=aircraft, role='owner').count()
                        if owner_count <= 1:
                            return Response(
                                {'error': 'Cannot demote the last owner.'},
                                status=status.HTTP_400_BAD_REQUEST)
                existing.role = role
                existing.save()
                log_event(aircraft, 'role',
                          f"Role updated: {role} for {target_user.username}",
                          user=request.user,
                          notes=f"by {request.user.username}")
            else:
                AircraftRole.objects.create(aircraft=aircraft, user=target_user, role=role)
                log_event(aircraft, 'role',
                          f"Role granted: {role} to {target_user.username}",
                          user=request.user,
                          notes=f"by {request.user.username}")

            roles = AircraftRole.objects.filter(aircraft=aircraft).select_related('user')
            return Response({
                'roles': AircraftRoleSerializer(roles, many=True).data,
            })

        if request.method == 'DELETE':
            user_id = request.data.get('user')
            if not user_id:
                return Response({'error': 'user is required.'},
                                status=status.HTTP_400_BAD_REQUEST)
            try:
                role_obj = AircraftRole.objects.select_related('user').get(
                    aircraft=aircraft, user_id=user_id)
            except (AircraftRole.DoesNotExist, ValueError):
                return Response({'error': 'Role not found.'},
                                status=status.HTTP_404_NOT_FOUND)

            # Self-removal prevention (non-admin)
            if role_obj.user == request.user and not request.user.is_staff:
                return Response({'error': 'Cannot remove your own role.'},
                                status=status.HTTP_400_BAD_REQUEST)

            # Last-owner protection (non-admin)
            if role_obj.role == 'owner' and not request.user.is_staff:
                owner_count = AircraftRole.objects.filter(
                    aircraft=aircraft, role='owner').count()
                if owner_count <= 1:
                    return Response({'error': 'Cannot remove the last owner.'},
                                    status=status.HTTP_400_BAD_REQUEST)

            target_username = role_obj.user.username
            role_obj.delete()
            log_event(aircraft, 'role',
                      f"Role removed: {target_username}",
                      user=request.user,
                      notes=f"by {request.user.username}")

            roles = AircraftRole.objects.filter(aircraft=aircraft).select_related('user')
            return Response({
                'roles': AircraftRoleSerializer(roles, many=True).data,
            })

    @action(detail=True, methods=['get', 'post'], url_path='share_tokens')
    def manage_share_tokens(self, request, pk=None):
        """
        List or create share tokens for an aircraft.
        GET  /api/aircraft/{id}/share_tokens/ - List all tokens
        POST /api/aircraft/{id}/share_tokens/ - Create a new token
        """
        aircraft = self.get_object()

        if request.method == 'GET':
            tokens = aircraft.share_tokens.all()
            return Response(
                AircraftShareTokenSerializer(tokens, many=True, context={'request': request}).data
            )

        # POST: create a new token
        privilege = request.data.get('privilege')
        if privilege not in ('status', 'maintenance'):
            return Response(
                {'error': 'privilege must be "status" or "maintenance".'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        label = request.data.get('label', '').strip()
        expires_at = None
        expires_in_days = request.data.get('expires_in_days')
        if expires_in_days is not None:
            try:
                days = int(expires_in_days)
            except (ValueError, TypeError):
                return Response({'error': 'expires_in_days must be an integer.'},
                                status=status.HTTP_400_BAD_REQUEST)
            if not (1 <= days <= 3650):
                return Response({'error': 'expires_in_days must be between 1 and 3650.'},
                                status=status.HTTP_400_BAD_REQUEST)
            expires_at = timezone.now() + td(days=days)

        with transaction.atomic():
            token_count = aircraft.share_tokens.select_for_update().count()
            if token_count >= 10:
                return Response(
                    {'error': 'Maximum of 10 share links per aircraft.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            token_obj = AircraftShareToken.objects.create(
                aircraft=aircraft,
                label=label,
                privilege=privilege,
                expires_at=expires_at,
                created_by=request.user,
            )
        log_event(
            aircraft, 'role',
            f"Share link created: {label or privilege}",
            user=request.user,
        )
        return Response(
            AircraftShareTokenSerializer(token_obj, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['delete'],
            url_path=r'share_tokens/(?P<token_id>[^/.]+)')
    def delete_share_token(self, request, pk=None, token_id=None):
        """
        Delete a share token.
        DELETE /api/aircraft/{id}/share_tokens/{token_id}/
        """
        aircraft = self.get_object()
        try:
            token_obj = AircraftShareToken.objects.get(id=token_id, aircraft=aircraft)
        except (AircraftShareToken.DoesNotExist, ValueError):
            return Response({'error': 'Share token not found.'}, status=status.HTTP_404_NOT_FOUND)

        label = token_obj.label or token_obj.privilege
        token_obj.delete()
        log_event(aircraft, 'role', f"Share link revoked: {label}", user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AircraftNoteViewSet(AircraftScopedMixin, EventLoggingMixin, viewsets.ModelViewSet):
    queryset = AircraftNote.objects.all().order_by('-added_timestamp')
    serializer_class = AircraftNoteSerializer
    aircraft_fk_path = 'aircraft'
    event_category = 'note'
    event_name_created = 'Note added'
    event_name_deleted = 'Note deleted'

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return AircraftNoteCreateUpdateSerializer
        return AircraftNoteNestedSerializer

    def perform_update(self, serializer):
        """Set edited_timestamp when note is updated"""
        instance = serializer.save(edited_timestamp=timezone.now())
        aircraft = instance.aircraft
        user = self.request.user if hasattr(self, 'request') else None
        log_event(aircraft, 'note', "Note updated", user=user)


class AircraftEventViewSet(viewsets.ReadOnlyModelViewSet):
    from rest_framework.pagination import PageNumberPagination

    class _Pagination(PageNumberPagination):
        page_size = 100
        max_page_size = 200

    queryset = AircraftEvent.objects.all()
    serializer_class = AircraftEventSerializer
    pagination_class = _Pagination

@require_GET
def healthz(request):
    return JsonResponse({"status": "ok"})


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard.html"


class AircraftDetailView(LoginRequiredMixin, TemplateView):
    template_name = 'aircraft_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['aircraft_id'] = self.kwargs['pk']
        context['base_template'] = 'base.html'
        import_models = list(settings.LOGBOOK_IMPORT_MODELS)
        extra = getattr(settings, 'LOGBOOK_IMPORT_EXTRA_MODELS', None)
        if extra:
            import json as _json
            try:
                import_models = import_models + _json.loads(extra)
            except (ValueError, TypeError):
                pass
        context['import_models'] = import_models
        context['import_default_model'] = getattr(settings, 'LOGBOOK_IMPORT_DEFAULT_MODEL', 'claude-sonnet-4-6')
        return context


class SquawkHistoryView(LoginRequiredMixin, TemplateView):
    template_name = 'squawk_history.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['aircraft_id'] = self.kwargs['pk']
        return context


class LogbookImportView(LoginRequiredMixin, View):
    """
    Web UI for importing scanned logbook pages.

    GET  /tools/import-logbook/                — render the form
    POST /tools/import-logbook/                — start a background import job
    GET  /tools/import-logbook/<job_id>/status/ — poll job progress
    """

    # Archive extensions we accept
    _ARCHIVE_SUFFIXES = {'.zip', '.tar', '.gz', '.bz2', '.xz', '.tgz'}
    _IMAGE_SUFFIXES = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff'}

    def get(self, request, job_id=None):
        if job_id:
            return self._job_status(request, job_id)
        # Only show aircraft the user owns (or all for admin)
        if request.user.is_staff or request.user.is_superuser:
            aircraft_list = Aircraft.objects.all().order_by('tail_number')
        else:
            owned_ids = AircraftRole.objects.filter(
                user=request.user, role='owner'
            ).values_list('aircraft_id', flat=True)
            aircraft_list = Aircraft.objects.filter(id__in=owned_ids).order_by('tail_number')
        import_models = settings.LOGBOOK_IMPORT_MODELS
        if not os.environ.get('ANTHROPIC_API_KEY'):
            import_models = [m for m in import_models if m.get('provider') != 'anthropic']
        default_model = settings.LOGBOOK_IMPORT_DEFAULT_MODEL
        available_ids = {m['id'] for m in import_models}
        if default_model not in available_ids:
            default_model = import_models[0]['id'] if import_models else ''
        return render(request, 'logbook_import.html', {
            'aircraft_list': aircraft_list,
            'import_models': import_models,
            'default_model': default_model,
            'ai_enabled': bool(import_models),
        })

    def post(self, request):
        tmpdir = None
        try:
            aircraft, error_response = self._resolve_aircraft(request)
            if error_response:
                return error_response

            tmpdir = tempfile.mkdtemp(prefix='sam_logbook_')
            image_paths, prep_error = self._prepare_images(request, tmpdir)
            if prep_error:
                return JsonResponse({'type': 'error', 'message': prep_error}, status=400)

            if not image_paths:
                return JsonResponse(
                    {'type': 'error', 'message': 'No supported image files found in upload.'},
                    status=400,
                )

            opts = self._parse_options(request)

            append_doc_id = opts.get('append_to_document_id')
            if append_doc_id:
                from health.models import Document
                try:
                    Document.objects.get(pk=append_doc_id, aircraft=aircraft)
                except (Document.DoesNotExist, ValueError):
                    return JsonResponse(
                        {'type': 'error',
                         'message': 'Document not found or does not belong to this aircraft.'},
                        status=400,
                    )

            from health.models import ImportJob
            job = ImportJob.objects.create(aircraft=aircraft, status='pending')

            # Hand tmpdir ownership to the background thread
            _tmpdir = tmpdir
            tmpdir = None

            from health.logbook_import import run_import_job
            t = threading.Thread(
                target=run_import_job,
                args=(job.id, _tmpdir, image_paths),
                kwargs={
                    'collection_name': opts['collection_name'],
                    'doc_name': opts['doc_name'],
                    'doc_type': opts['doc_type'],
                    'model': opts['model'],
                    'provider': opts['provider'],
                    'upload_only': opts['upload_only'],
                    'log_type_override': opts['log_type_override'] or None,
                    'batch_size': opts['batch_size'],
                    'append_to_document_id': append_doc_id,
                },
                daemon=True,
            )
            t.start()

            return JsonResponse({'job_id': str(job.id)})

        except Exception:
            logger.exception("Unhandled error in LogbookImportView.post")
            return JsonResponse({'type': 'error', 'message': 'An unexpected error occurred.'}, status=500)
        finally:
            if tmpdir:
                shutil.rmtree(tmpdir, ignore_errors=True)

    def _job_status(self, request, job_id):
        from health.models import ImportJob
        try:
            job = ImportJob.objects.get(pk=job_id)
        except ImportJob.DoesNotExist:
            return JsonResponse({'error': 'Job not found'}, status=404)

        try:
            after = int(request.GET.get('after', 0))
        except (ValueError, TypeError):
            after = 0

        new_events = job.events[after:]

        return JsonResponse({
            'status': job.status,
            'events': new_events,
            'result': job.result,
        })

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _resolve_aircraft(self, request):
        aircraft_id = request.POST.get('aircraft')
        if not aircraft_id:
            return None, JsonResponse({'type': 'error', 'message': 'aircraft is required'}, status=400)
        try:
            aircraft = Aircraft.objects.get(pk=aircraft_id)
        except (Aircraft.DoesNotExist, ValueError):
            return None, JsonResponse({'type': 'error', 'message': 'Aircraft not found'}, status=404)
        if not has_aircraft_permission(request.user, aircraft, 'owner'):
            return None, JsonResponse({'type': 'error', 'message': 'Permission denied'}, status=403)
        return aircraft, None

    def _prepare_images(self, request, tmpdir: str):
        """
        Write uploaded files into tmpdir and return a sorted list of image Paths.
        Handles two upload modes:
          - file_mode='images': multiple image files in request.FILES.getlist('images')
          - file_mode='archive': single zip/tar in request.FILES['archive']
        """
        file_mode = request.POST.get('file_mode', 'images')

        if file_mode == 'archive':
            archive_file = request.FILES.get('archive')
            if not archive_file:
                return None, 'No archive file uploaded.'
            error = self._extract_archive(archive_file, tmpdir)
            if error:
                return None, error
        else:
            uploaded = request.FILES.getlist('images')
            if not uploaded:
                return None, 'No image files uploaded.'
            if len(uploaded) > self._MAX_IMAGE_COUNT:
                return None, (
                    f"Too many images uploaded ({len(uploaded)}). "
                    f"Maximum is {self._MAX_IMAGE_COUNT} per request."
                )
            for uf in uploaded:
                dest = Path(tmpdir) / uf.name
                with open(dest, 'wb') as fh:
                    for chunk in uf.chunks():
                        fh.write(chunk)

        image_paths = sorted(
            p for p in Path(tmpdir).rglob('*')
            if p.is_file() and p.suffix.lower() in self._IMAGE_SUFFIXES
        )
        return image_paths, None

    def _extract_archive(self, archive_file, tmpdir: str):
        """
        Extract a zip or tar archive into tmpdir.
        Returns an error string on failure, None on success.
        Guards against path-traversal (zip-slip) attacks.
        """
        name = archive_file.name.lower()

        # Write upload to a temp file so we can seek for format detection
        tmp_archive = os.path.join(tmpdir, '_upload_archive')
        with open(tmp_archive, 'wb') as fh:
            for chunk in archive_file.chunks():
                fh.write(chunk)

        real_tmpdir = os.path.realpath(tmpdir)

        if zipfile.is_zipfile(tmp_archive):
            try:
                with zipfile.ZipFile(tmp_archive) as zf:
                    members = [m for m in zf.infolist() if not m.filename.endswith('/')]
                    if len(members) > self._MAX_ARCHIVE_MEMBERS:
                        return (
                            f"Archive contains too many files ({len(members)}). "
                            f"Maximum is {self._MAX_ARCHIVE_MEMBERS}."
                        )
                    total_bytes = 0
                    for member in members:
                        total_bytes += member.file_size
                        if total_bytes > self._MAX_ARCHIVE_BYTES:
                            return (
                                f"Archive decompressed size exceeds the "
                                f"{self._MAX_ARCHIVE_BYTES // (1024 * 1024)} MB limit."
                            )
                        target = os.path.realpath(
                            os.path.join(real_tmpdir, member.filename)
                        )
                        if not target.startswith(real_tmpdir + os.sep):
                            continue  # skip path-traversal attempts
                        os.makedirs(os.path.dirname(target), exist_ok=True)
                        with zf.open(member) as src, open(target, 'wb') as dst:
                            dst.write(src.read())
            except zipfile.BadZipFile as exc:
                return "Invalid ZIP file."
        elif tarfile.is_tarfile(tmp_archive):
            try:
                with tarfile.open(tmp_archive) as tf:
                    file_members = [m for m in tf.getmembers() if m.isfile()]
                    if len(file_members) > self._MAX_ARCHIVE_MEMBERS:
                        return (
                            f"Archive contains too many files ({len(file_members)}). "
                            f"Maximum is {self._MAX_ARCHIVE_MEMBERS}."
                        )
                    total_bytes = 0
                    for member in file_members:
                        total_bytes += member.size
                        if total_bytes > self._MAX_ARCHIVE_BYTES:
                            return (
                                f"Archive decompressed size exceeds the "
                                f"{self._MAX_ARCHIVE_BYTES // (1024 * 1024)} MB limit."
                            )
                        target = os.path.realpath(
                            os.path.join(real_tmpdir, member.name)
                        )
                        if not target.startswith(real_tmpdir + os.sep):
                            continue  # skip path-traversal attempts
                        os.makedirs(os.path.dirname(target), exist_ok=True)
                        src = tf.extractfile(member)
                        if src:
                            with open(target, 'wb') as dst:
                                dst.write(src.read())
            except tarfile.TarError as exc:
                return "Invalid archive file."
        else:
            return f"Unrecognised archive format for file: {archive_file.name}"

        os.remove(tmp_archive)
        return None

    _ALLOWED_BATCH_SIZE_MIN = 1
    _ALLOWED_BATCH_SIZE_MAX = 20

    # Max number of images accepted per request (images mode)
    _MAX_IMAGE_COUNT = 100
    # Max total decompressed bytes from an archive
    _MAX_ARCHIVE_BYTES = 2048 * 1024 * 1024  # 2048 MB
    # Max members in an archive
    _MAX_ARCHIVE_MEMBERS = 200

    @staticmethod
    def _parse_options(request):
        def _int(key, default):
            try:
                return int(request.POST.get(key, default))
            except (ValueError, TypeError):
                return default

        upload_only_raw = request.POST.get('upload_only', 'false')
        upload_only = upload_only_raw.lower() in ('true', '1', 'on', 'yes')

        collection_name = request.POST.get('collection_name', '').strip()
        doc_name = request.POST.get('doc_name', '').strip()

        # Fall back to a generic name if the client sent nothing
        if not collection_name:
            collection_name = 'Imported Logbook'
        if not doc_name:
            doc_name = collection_name

        # Validate model against settings registry
        model_registry = {m['id']: m for m in settings.LOGBOOK_IMPORT_MODELS}
        default_model = settings.LOGBOOK_IMPORT_DEFAULT_MODEL
        requested_model = request.POST.get('model', default_model)
        if requested_model not in model_registry:
            requested_model = default_model
        provider = model_registry.get(requested_model, {}).get('provider', 'anthropic')

        # Clamp batch_size to safe range server-side
        batch_size = max(
            LogbookImportView._ALLOWED_BATCH_SIZE_MIN,
            min(
                _int('batch_size', 10),
                LogbookImportView._ALLOWED_BATCH_SIZE_MAX,
            ),
        )

        return {
            'collection_name': collection_name,
            'doc_name': doc_name,
            'doc_type': request.POST.get('doc_type', 'LOG'),
            'model': requested_model,
            'provider': provider,
            'upload_only': upload_only,
            'log_type_override': request.POST.get('log_type_override', ''),
            'batch_size': batch_size,
            'append_to_document_id': request.POST.get('append_to_document_id', '').strip() or None,
        }


class PublicAircraftView(TemplateView):
    """Read-only public view of an aircraft via share token."""
    template_name = 'aircraft_detail.html'

    def get(self, request, share_token, *args, **kwargs):
        from django.http import Http404
        try:
            token_obj = AircraftShareToken.objects.select_related('aircraft').get(token=share_token)
        except AircraftShareToken.DoesNotExist:
            raise Http404
        if token_obj.expires_at and token_obj.expires_at < timezone.now():
            raise Http404
        aircraft = token_obj.aircraft
        return render(request, self.template_name, {
            'aircraft_id': str(aircraft.id),
            'share_token': str(share_token),
            'privilege_level': token_obj.privilege,
            'base_template': 'base_public.html',
        })


class PublicAircraftSummaryAPI(View):
    """Public API endpoint that returns aircraft summary data for shared links."""

    def get(self, request, share_token):
        try:
            token_obj = AircraftShareToken.objects.select_related('aircraft').get(token=share_token)
        except AircraftShareToken.DoesNotExist:
            return JsonResponse({'error': 'Not found'}, status=404)
        if token_obj.expires_at and token_obj.expires_at < timezone.now():
            return JsonResponse({'error': 'Not found'}, status=404)
        aircraft = token_obj.aircraft
        privilege = token_obj.privilege

        from rest_framework.request import Request
        from rest_framework.parsers import JSONParser

        drf_request = Request(request, parsers=[JSONParser()])

        current_hours = aircraft.flight_time
        today = date_cls.today()

        # Build AD status list (same logic as AircraftViewSet.ads GET)
        component_ids = aircraft.components.values_list('id', flat=True)
        aircraft_ads = AD.objects.filter(applicable_aircraft=aircraft)
        component_ads = AD.objects.filter(applicable_component__in=component_ids)
        all_ads = (aircraft_ads | component_ads).distinct()

        ads_data = []
        for ad in all_ads:
            ad_dict = ADNestedSerializer(ad).data
            compliance = ADCompliance.objects.filter(ad=ad).filter(
                Q(aircraft=aircraft) | Q(component__aircraft=aircraft)
            ).order_by('-date_complied').first()
            ad_dict['latest_compliance'] = ADComplianceNestedSerializer(compliance).data if compliance else None
            if ad.compliance_type == 'conditional':
                ad_dict['compliance_status'] = 'compliant' if compliance else 'conditional'
            elif not compliance:
                ad_dict['compliance_status'] = 'no_compliance'
            elif compliance.permanent:
                ad_dict['compliance_status'] = 'compliant'
            else:
                rank, extras = ad_compliance_status(ad, compliance, current_hours, today)
                ad_dict.update(extras)
                ad_dict['compliance_status'] = STATUS_LABELS[rank]
            # Include full compliance history only for maintenance privilege
            if privilege == 'maintenance':
                all_compliances = ADCompliance.objects.filter(ad=ad).filter(
                    Q(aircraft=aircraft) | Q(component__aircraft=aircraft)
                ).order_by('-date_complied')
                ad_dict['compliance_history'] = ADComplianceNestedSerializer(all_compliances, many=True).data
            ads_data.append(ad_dict)

        # Build inspection status list (same logic as AircraftViewSet.inspections GET)
        aircraft_inspections = InspectionType.objects.filter(applicable_aircraft=aircraft)
        component_inspections = InspectionType.objects.filter(applicable_component__in=component_ids)
        all_types = (aircraft_inspections | component_inspections).distinct()

        inspections_data = []
        for insp_type in all_types:
            type_dict = InspectionTypeNestedSerializer(insp_type).data
            last_record = InspectionRecord.objects.filter(inspection_type=insp_type).filter(
                Q(aircraft=aircraft) | Q(component__aircraft=aircraft)
            ).order_by('-date').first()
            type_dict['latest_record'] = InspectionRecordNestedSerializer(last_record).data if last_record else None
            if not last_record:
                type_dict['compliance_status'] = 'never_completed'
            else:
                rank, extras = inspection_compliance_status(insp_type, last_record, current_hours, today)
                type_dict.update(extras)
                type_dict['compliance_status'] = STATUS_LABELS[rank]
            # Include full inspection history only for maintenance privilege
            if privilege == 'maintenance':
                all_records = InspectionRecord.objects.filter(inspection_type=insp_type).filter(
                    Q(aircraft=aircraft) | Q(component__aircraft=aircraft)
                ).order_by('-date')
                type_dict['inspection_history'] = InspectionRecordNestedSerializer(all_records, many=True).data
            inspections_data.append(type_dict)

        # Build document collections and uncollected documents (shared only).
        # Visibility levels: 'status' (all share links), 'maintenance' (maintenance tokens only).
        # A document's effective visibility: use doc.visibility if set, else inherit from collection.
        def _doc_visible(doc_vis, col_vis):
            effective = doc_vis if doc_vis is not None else col_vis
            if not effective or effective == 'private':
                return False
            if effective == 'maintenance':
                return privilege == 'maintenance'
            return True  # 'status' — visible to all share links

        all_collections = DocumentCollection.objects.filter(aircraft=aircraft).prefetch_related('documents__images')
        collections = []
        for col in all_collections:
            if col.visibility == 'private':
                continue
            if col.visibility == 'maintenance' and privilege != 'maintenance':
                continue
            visible_docs = [
                d for d in col.documents.all()
                if _doc_visible(d.visibility, col.visibility)
            ]
            if visible_docs:
                col._visible_documents = visible_docs
                collections.append(col)
        uncollected_qs = Document.objects.filter(
            aircraft=aircraft, collection__isnull=True
        ).exclude(visibility__isnull=True).exclude(visibility='private').prefetch_related('images')
        uncollected_docs = [d for d in uncollected_qs if _doc_visible(d.visibility, None)]

        # Major records and linked logbook entries: maintenance privilege only
        if privilege == 'maintenance':
            major_records_data = MajorRepairAlterationNestedSerializer(
                MajorRepairAlteration.objects.filter(aircraft=aircraft),
                many=True
            ).data

            # Collect IDs of every logbook entry referenced by any linked record in the response
            linked_ids = set()
            for mr in major_records_data:
                if mr.get('logbook_entry'):
                    linked_ids.add(mr['logbook_entry'])
            for ad_dict in ads_data:
                for rec in ad_dict.get('compliance_history', []):
                    if rec.get('logbook_entry'):
                        linked_ids.add(rec['logbook_entry'])
            for insp_dict in inspections_data:
                for rec in insp_dict.get('inspection_history', []):
                    if rec.get('logbook_entry'):
                        linked_ids.add(rec['logbook_entry'])

            linked_logbook_entries = LogbookEntrySerializer(
                LogbookEntry.objects.filter(id__in=linked_ids),
                many=True, context={'request': drf_request}
            ).data if linked_ids else []
        else:
            major_records_data = []
            linked_logbook_entries = []

        summary_data = {
            'aircraft': AircraftSerializer(aircraft, context={'request': drf_request}).data,
            'components': ComponentSerializer(
                aircraft.components.all(), many=True,
                context={'request': drf_request}
            ).data,
            'linked_logbook_entries': linked_logbook_entries,
            'active_squawks': SquawkNestedSerializer(
                aircraft.squawks.filter(resolved=False),
                many=True, context={'request': drf_request}
            ).data,
            'resolved_squawks': SquawkNestedSerializer(
                aircraft.squawks.filter(resolved=True).order_by('-created_at'),
                many=True, context={'request': drf_request}
            ).data if privilege == 'maintenance' else [],
            'notes': AircraftNoteNestedSerializer(
                aircraft.notes.filter(public=True).order_by('-added_timestamp'),
                many=True, context={'request': drf_request}
            ).data,
            'ads': ads_data,
            'inspections': inspections_data,
            'oil_records': ConsumableRecordNestedSerializer(
                aircraft.consumable_records.filter(
                    record_type=ConsumableRecord.RECORD_TYPE_OIL
                ).order_by('-flight_hours')[:21],
                many=True
            ).data,
            'fuel_records': ConsumableRecordNestedSerializer(
                aircraft.consumable_records.filter(
                    record_type=ConsumableRecord.RECORD_TYPE_FUEL
                ).order_by('-flight_hours')[:21],
                many=True
            ).data,
            'document_collections': [
                {
                    **DocumentCollectionNestedSerializer(col).data,
                    'documents': DocumentNestedSerializer(col._visible_documents, many=True).data,
                    'document_count': len(col._visible_documents),
                }
                for col in collections
            ],
            'documents': DocumentNestedSerializer(uncollected_docs, many=True).data,
            'major_records': major_records_data,
            'oil_analysis_reports': OilAnalysisReportSerializer(
                OilAnalysisReport.objects.filter(aircraft=aircraft).select_related('component__component_type'),
                many=True,
            ).data if privilege == 'maintenance' else [],
        }

        # Build set of publicly visible document IDs
        visible_doc_ids = set()
        for col in collections:
            for d in col._visible_documents:
                visible_doc_ids.add(str(d.id))
        for d in uncollected_docs:
            visible_doc_ids.add(str(d.id))

        # Strip non-public document UUIDs from major records so private document
        # IDs are not disclosed to anonymous viewers of a share link.
        for record in summary_data['major_records']:
            for doc_field, name_field in (
                ('form_337_document', 'form_337_document_name'),
                ('stc_document', 'stc_document_name'),
            ):
                doc_id = record.get(doc_field)
                if doc_id and str(doc_id) not in visible_doc_ids:
                    record[doc_field] = None
                    record[name_field] = None

        # Annotate linked logbook entries with document visibility for public view
        for log_entry in summary_data['linked_logbook_entries']:
            # log_image is a hyperlinked URL — extract the document ID
            log_image_url = log_entry.get('log_image')
            if log_image_url:
                m = re.search(r'/([0-9a-f-]{36})/?$', log_image_url, re.I)
                log_entry['log_image_shared'] = bool(m and m.group(1) in visible_doc_ids)
            else:
                log_entry['log_image_shared'] = False

            # Filter related_documents_detail to only publicly visible docs
            rdocs = log_entry.get('related_documents_detail', [])
            log_entry['related_documents_detail'] = [
                rd for rd in rdocs if str(rd.get('id', '')) in visible_doc_ids
            ]

        # Strip sensitive fields
        aircraft_data = summary_data['aircraft']
        for field in ('has_share_links', 'roles'):
            aircraft_data.pop(field, None)
        aircraft_data['user_role'] = None

        return JsonResponse(summary_data)


class PublicLogbookEntriesAPI(View):
    """Paginated public endpoint for browsing logbook entries on a shared aircraft."""

    def get(self, request, share_token):
        try:
            token_obj = AircraftShareToken.objects.select_related('aircraft').get(token=share_token)
        except AircraftShareToken.DoesNotExist:
            return JsonResponse({'error': 'Not found'}, status=404)
        if token_obj.expires_at and token_obj.expires_at < timezone.now():
            return JsonResponse({'error': 'Not found'}, status=404)
        if token_obj.privilege == 'status':
            return JsonResponse({'error': 'Not found'}, status=404)
        aircraft = token_obj.aircraft

        try:
            limit = min(int(request.GET.get('limit', 50)), 200)
            offset = max(int(request.GET.get('offset', 0)), 0)
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Invalid pagination parameters'}, status=400)

        from rest_framework.request import Request
        from rest_framework.parsers import JSONParser
        drf_request = Request(request, parsers=[JSONParser()])

        qs = aircraft.logbook_entries.order_by('-date', 'id')

        # Filter params (same field names the private endpoint uses)
        log_type = request.GET.get('log_type', '').strip()
        entry_type = request.GET.get('entry_type', '').strip()
        search = request.GET.get('search', '').strip()

        VALID_LOG_TYPES = {'AC', 'ENG', 'PROP', 'OTHER'}
        VALID_ENTRY_TYPES = {'MAINTENANCE', 'INSPECTION', 'FLIGHT', 'HOURS_UPDATE', 'OTHER'}

        if log_type in VALID_LOG_TYPES:
            qs = qs.filter(log_type=log_type)
        if entry_type in VALID_ENTRY_TYPES:
            qs = qs.filter(entry_type=entry_type)
        if search:
            from django.db.models import Q
            qs = qs.filter(Q(text__icontains=search) | Q(signoff_person__icontains=search))

        total = qs.count()
        entries = LogbookEntrySerializer(
            qs[offset:offset + limit], many=True, context={'request': drf_request}
        ).data

        # Apply the same log_image_shared annotation used in the summary endpoint.
        # This endpoint is maintenance-privilege only, so both 'status' and 'maintenance' docs are visible.
        all_collections = DocumentCollection.objects.filter(aircraft=aircraft).prefetch_related('documents')
        visible_doc_ids = set()
        for col in all_collections:
            if col.visibility in ('status', 'maintenance'):
                for d in col.documents.all():
                    effective = d.visibility if d.visibility is not None else col.visibility
                    if effective in ('status', 'maintenance'):
                        visible_doc_ids.add(str(d.id))
        uncollected = Document.objects.filter(
            aircraft=aircraft, collection__isnull=True, visibility__in=('status', 'maintenance')
        )
        for d in uncollected:
            visible_doc_ids.add(str(d.id))

        for log_entry in entries:
            log_image_url = log_entry.get('log_image')
            if log_image_url:
                m = re.search(r'/([0-9a-f-]{36})/?$', log_image_url, re.I)
                log_entry['log_image_shared'] = bool(m and m.group(1) in visible_doc_ids)
            else:
                log_entry['log_image_shared'] = False
            rdocs = log_entry.get('related_documents_detail', [])
            log_entry['related_documents_detail'] = [
                rd for rd in rdocs if str(rd.get('id', '')) in visible_doc_ids
            ]

        return JsonResponse({'results': entries, 'count': total, 'offset': offset, 'limit': limit})


def custom_logout(request):
    """
    Custom logout view that handles both OIDC and Django sessions.

    If the user has an OIDC session (indicated by oidc_id_token in session),
    redirect to the Keycloak logout endpoint to clear both sessions.
    Otherwise, perform standard Django logout.
    """
    # Check if OIDC is enabled and user has OIDC session
    if getattr(settings, 'OIDC_ENABLED', False) and 'oidc_id_token' in request.session:
        # Import here to avoid issues when mozilla_django_oidc is not installed
        from core.oidc import provider_logout

        # Get Keycloak logout URL
        logout_url = provider_logout(request)

        # Clear Django session
        logout(request)

        # Redirect to Keycloak logout (which will redirect back to our app)
        if logout_url:
            return redirect(logout_url)

    # Standard Django logout (for local users or if OIDC disabled)
    logout(request)
    return redirect('/')


class ExportView(LoginRequiredMixin, View):
    """
    GET /api/aircraft/{pk}/export/
    Streams a .sam.zip archive for the given aircraft.
    Only the aircraft owner or admin may export.
    """

    def get(self, request, pk):
        import io
        from django.http import StreamingHttpResponse, Http404
        from core.export import export_aircraft_zip, build_manifest

        try:
            aircraft = Aircraft.objects.get(pk=pk)
        except (Aircraft.DoesNotExist, ValueError):
            raise Http404

        if not has_aircraft_permission(request.user, aircraft, 'owner'):
            return JsonResponse({'error': 'Permission denied'}, status=403)

        from datetime import date as date_cls
        filename = f"{aircraft.tail_number}_{date_cls.today().strftime('%Y%m%d')}.sam.zip"

        # Build the ZIP into a BytesIO buffer and stream it
        buf = io.BytesIO()
        export_aircraft_zip(aircraft, buf)
        buf.seek(0)

        log_event(aircraft=aircraft, category='aircraft', event_name='Aircraft exported', user=request.user)

        response = StreamingHttpResponse(
            buf,
            content_type='application/zip',
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class ImportView(LoginRequiredMixin, View):
    """
    POST /api/aircraft/import/
    Stage the uploaded archive and start a background import job.
    Returns 202 with {"job_id": "..."} on acceptance.
    Returns 400 on validation failure.
    Returns 403 if the user is not permitted to create aircraft.
    Returns 409 on tail-number conflict with {"error": "tail_number_conflict", ...}.
    """

    def post(self, request):
        import threading
        from core.import_export import validate_archive_quick, run_aircraft_import_job
        from health.models import ImportJob

        if not user_can_create_aircraft(request.user):
            return JsonResponse({'error': 'You do not have permission to import aircraft.'}, status=403)

        max_size = getattr(settings, 'IMPORT_MAX_ARCHIVE_SIZE', 10 * 1024 * 1024 * 1024)
        staging_dir = getattr(settings, 'IMPORT_STAGING_DIR', os.path.join(settings.BASE_DIR, 'import_staging'))
        os.makedirs(staging_dir, exist_ok=True)

        staged_id = request.POST.get('staged_id', '').strip()
        tail_number_override = request.POST.get('tail_number', '').strip() or None

        # Determine ZIP path — either from a previously staged file or a new upload
        if staged_id:
            # Retry path: archive was already staged
            try:
                uuid.UUID(staged_id)
            except ValueError:
                return JsonResponse({'error': 'Invalid staged_id.'}, status=400)
            zip_path = os.path.join(staging_dir, f"{staged_id}.zip")
            if not os.path.exists(zip_path):
                return JsonResponse({'error': 'Staged archive not found. Please re-upload the file.'}, status=400)
        else:
            archive_file = request.FILES.get('archive')
            if not archive_file:
                return JsonResponse({'error': 'No archive file provided.'}, status=400)

            # Size check
            if archive_file.size > max_size:
                return JsonResponse(
                    {'error': f"Archive exceeds the {max_size // (1024 ** 3)} GiB size limit."},
                    status=400,
                )

            # Pre-flight disk space check: need at least 2× archive size free
            try:
                free = shutil.disk_usage(staging_dir).free
                if free < 2 * archive_file.size:
                    return JsonResponse(
                        {'error': 'Insufficient disk space to stage the archive.'},
                        status=400,
                    )
            except OSError:
                pass  # Can't check; proceed anyway

            new_staged_id = str(uuid.uuid4())
            zip_path = os.path.join(staging_dir, f"{new_staged_id}.zip")
            try:
                with open(zip_path, 'wb') as fh:
                    for chunk in archive_file.chunks():
                        fh.write(chunk)
            except OSError as exc:
                logger.exception("Failed to stage import archive: %s", exc)
                return JsonResponse({'error': 'Failed to stage the archive. Please try again.'}, status=500)
            staged_id = new_staged_id

        # Quick synchronous validation
        manifest, effective_tail, error = validate_archive_quick(zip_path, tail_number_override)

        if error == 'CONFLICT':
            # Return 409 with staged_id so client can retry without re-uploading
            return JsonResponse({
                'error': 'tail_number_conflict',
                'tail_number': effective_tail,
                'staged_id': staged_id,
            }, status=409)

        if error:
            # Clean up staged file on hard validation failure
            try:
                os.remove(zip_path)
            except OSError:
                pass
            return JsonResponse({'error': error}, status=400)

        # Create the ImportJob and start background thread
        job = ImportJob.objects.create(status='pending', user=request.user)

        t = threading.Thread(
            target=run_aircraft_import_job,
            args=(job.id, zip_path, request.user),
            kwargs={'tail_number_override': tail_number_override},
            daemon=True,
        )
        t.start()

        return JsonResponse({'job_id': str(job.id)}, status=202)


class ImportJobStatusView(LoginRequiredMixin, View):
    """
    GET /api/aircraft/import/{job_id}/
    Poll the status of an aircraft import job.
    Only the submitting user may poll.
    """

    def get(self, request, job_id):
        from health.models import ImportJob

        try:
            job = ImportJob.objects.get(pk=job_id)
        except ImportJob.DoesNotExist:
            return JsonResponse({'error': 'Job not found'}, status=404)

        # Only the submitting user (or admin) may view this job
        if not request.user.is_staff and not request.user.is_superuser:
            if job.user_id != request.user.pk:
                return JsonResponse({'error': 'Job not found'}, status=404)

        try:
            after = int(request.GET.get('after', 0))
        except (ValueError, TypeError):
            after = 0

        return JsonResponse({
            'status': job.status,
            'events': job.events[after:],
            'result': job.result,
        })


class RegisterView(View):
    """Redeem an invitation code and create a local account."""

    def _get_code(self, token):
        try:
            return InvitationCode.objects.get(token=token)
        except InvitationCode.DoesNotExist:
            return None

    def get(self, request, token):
        if request.user.is_authenticated:
            return redirect('dashboard')

        code = self._get_code(token)
        if code is None or not code.is_valid:
            return render(request, 'registration/register.html', {'invalid': True})

        form = RegistrationForm(invited_email=code.invited_email, invited_name=code.invited_name)
        return render(request, 'registration/register.html', {'form': form, 'code': code})

    def post(self, request, token):
        if request.user.is_authenticated:
            return redirect('dashboard')

        code = self._get_code(token)
        if code is None or not code.is_valid:
            return render(request, 'registration/register.html', {'invalid': True})

        form = RegistrationForm(
            request.POST,
            invited_email=code.invited_email,
            invited_name=code.invited_name,
        )
        if not form.is_valid():
            return render(request, 'registration/register.html', {'form': form, 'code': code})

        try:
            with transaction.atomic():
                user = form.save()

                # Re-fetch with a row-level lock to prevent concurrent over-redemption
                code = InvitationCode.objects.select_for_update().get(pk=code.pk)
                if not code.is_valid:
                    raise ValueError("Invitation code is no longer valid")

                InvitationCodeRedemption.objects.create(code=code, user=user)
                InvitationCode.objects.filter(pk=code.pk).update(use_count=F('use_count') + 1)

                # Grant any configured initial aircraft roles
                for initial_role in code.initial_roles.select_related('aircraft').all():
                    AircraftRole.objects.get_or_create(
                        aircraft=initial_role.aircraft,
                        user=user,
                        defaults={'role': initial_role.role},
                    )
        except ValueError:
            return render(request, 'registration/register.html', {'invalid': True})

        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        return redirect('dashboard')


class ProfileView(LoginRequiredMixin, View):
    """Allow local-account users to edit their own profile."""

    def _check_local_account(self, request):
        """Return None if the user has a local account, or a redirect if not."""
        if not request.user.has_usable_password():
            return redirect('dashboard')
        return None

    def get(self, request):
        if redirect_response := self._check_local_account(request):
            return redirect_response
        form = UserProfileForm(instance=request.user)
        return render(request, 'core/profile.html', {'form': form})

    def post(self, request):
        if redirect_response := self._check_local_account(request):
            return redirect_response
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            return render(request, 'core/profile.html', {'form': form, 'saved': True})
        return render(request, 'core/profile.html', {'form': form})


class UserSearchView(APIView):
    """Search users by username or full name for role assignment."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        q = request.query_params.get('q', '').strip()
        if len(q) < 2:
            return Response([])
        users = User.objects.filter(
            Q(username__icontains=q) |
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q)
        ).order_by('username')[:10]
        results = []
        for u in users:
            full_name = f"{u.first_name} {u.last_name}".strip()
            results.append({
                'id': str(u.pk),
                'username': u.username,
                'display': f"{u.username} ({full_name})" if full_name else u.username,
            })
        return Response(results)


class InvitationCodeViewSet(viewsets.ModelViewSet):
    queryset = InvitationCode.objects.all().order_by('-created_at').prefetch_related(
        'initial_roles__aircraft', 'redemptions__user'
    )
    serializer_class = InvitationCodeSerializer

    def get_permissions(self):
        return [IsAdminUser()]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return InvitationCodeDetailSerializer
        return InvitationCodeSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'], url_path='toggle_active')
    def toggle_active(self, request, pk=None):
        code = self.get_object()
        code.is_active = not code.is_active
        code.save()
        return Response(InvitationCodeSerializer(code, context={'request': request}).data)


class InvitationCodeAircraftRoleViewSet(viewsets.ModelViewSet):
    queryset = InvitationCodeAircraftRole.objects.all()
    serializer_class = InvitationCodeAircraftRoleSerializer

    def get_permissions(self):
        return [IsAdminUser()]

    def list(self, request, *args, **kwargs):
        from rest_framework.exceptions import MethodNotAllowed
        raise MethodNotAllowed('GET')

    def retrieve(self, request, *args, **kwargs):
        from rest_framework.exceptions import MethodNotAllowed
        raise MethodNotAllowed('GET')

    def update(self, request, *args, **kwargs):
        from rest_framework.exceptions import MethodNotAllowed
        raise MethodNotAllowed('PUT')

    def partial_update(self, request, *args, **kwargs):
        from rest_framework.exceptions import MethodNotAllowed
        raise MethodNotAllowed('PATCH')


class ManageInvitationsView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'manage/invitations.html'

    def test_func(self):
        return self.request.user.is_staff


class ManageInvitationDetailView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'manage/invitation_detail.html'

    def test_func(self):
        return self.request.user.is_staff

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['invitation_id'] = str(self.kwargs['pk'])
        return context


class ManageUsersView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'manage/users.html'

    def test_func(self):
        return self.request.user.is_staff

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['users'] = User.objects.all().prefetch_related(
            Prefetch('aircraft_roles', queryset=AircraftRole.objects.select_related('aircraft'))
        ).order_by('username')
        return context
