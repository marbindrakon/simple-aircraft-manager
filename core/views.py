import json
import os
import shutil
import tarfile
import tempfile
import threading
import zipfile
from datetime import date as date_cls, timedelta as td
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth import logout
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views import View
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from core.events import log_event
from core.mixins import EventLoggingMixin
from core.models import Aircraft, AircraftNote, AircraftEvent
from core.serializers import (
    AircraftSerializer, AircraftListSerializer, AircraftNoteSerializer,
    AircraftNoteNestedSerializer, AircraftNoteCreateUpdateSerializer,
    AircraftEventSerializer, AircraftEventNestedSerializer,
)
from health.models import (
    Component, LogbookEntry, Squawk, Document, DocumentCollection,
    ConsumableRecord, AD, ADCompliance, InspectionType, InspectionRecord,
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
)
from health.services import (
    end_of_month_after, ad_compliance_status, inspection_compliance_status,
    STATUS_LABELS,
)


class AircraftViewSet(viewsets.ModelViewSet):
    queryset = Aircraft.objects.all()
    serializer_class = AircraftSerializer

    def get_serializer_class(self):
        """Use lightweight serializer for list, full serializer for detail."""
        if self.action == 'list':
            return AircraftListSerializer
        return AircraftSerializer

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
        except:
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
                except AD.DoesNotExist:
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
        except AD.DoesNotExist:
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
                except InspectionType.DoesNotExist:
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
        except InspectionType.DoesNotExist:
            return Response({'error': 'InspectionType not found'}, status=status.HTTP_404_NOT_FOUND)

        insp_type.applicable_aircraft.remove(aircraft)
        return Response({'success': True})


class AircraftNoteViewSet(EventLoggingMixin, viewsets.ModelViewSet):
    queryset = AircraftNote.objects.all().order_by('-added_timestamp')
    serializer_class = AircraftNoteSerializer
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
    queryset = AircraftEvent.objects.all()
    serializer_class = AircraftEventSerializer

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
        aircraft_list = Aircraft.objects.all().order_by('tail_number')
        return render(request, 'logbook_import.html', {'aircraft_list': aircraft_list})

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
                    'upload_only': opts['upload_only'],
                    'log_type_override': opts['log_type_override'] or None,
                    'batch_size': opts['batch_size'],
                },
                daemon=True,
            )
            t.start()

            return JsonResponse({'job_id': str(job.id)})

        except Exception:
            import logging
            logging.getLogger(__name__).exception("Unhandled error in LogbookImportView.post")
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

    _ALLOWED_MODELS = {
        'claude-haiku-4-5-20251001',
        'claude-sonnet-4-5-20250929',
        'claude-opus-4-6',
    }
    _DEFAULT_MODEL = 'claude-sonnet-4-5-20250929'

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

        # Validate model against server-side allowlist
        requested_model = request.POST.get('model', LogbookImportView._DEFAULT_MODEL)
        if requested_model not in LogbookImportView._ALLOWED_MODELS:
            requested_model = LogbookImportView._DEFAULT_MODEL

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
            'upload_only': upload_only,
            'log_type_override': request.POST.get('log_type_override', ''),
            'batch_size': batch_size,
        }


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
