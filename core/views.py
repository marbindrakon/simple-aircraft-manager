from datetime import date as date_cls, timedelta as td
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import logout
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from core.models import Aircraft, AircraftNote, AircraftEvent
from core.serializers import (
    AircraftSerializer, AircraftListSerializer, AircraftNoteSerializer,
    AircraftNoteNestedSerializer, AircraftNoteCreateUpdateSerializer,
    AircraftEventSerializer,
)
from health.models import (
    Component, LogbookEntry, Squawk, Document, DocumentCollection,
    OilRecord, FuelRecord, AD, ADCompliance, InspectionType, InspectionRecord,
)
from health.serializers import (
    ComponentSerializer, ComponentCreateUpdateSerializer,
    LogbookEntrySerializer, SquawkSerializer,
    SquawkNestedSerializer, SquawkCreateUpdateSerializer,
    DocumentCollectionNestedSerializer, DocumentNestedSerializer,
    OilRecordNestedSerializer, OilRecordCreateSerializer,
    FuelRecordNestedSerializer, FuelRecordCreateSerializer,
    ADNestedSerializer, ADComplianceNestedSerializer, ADComplianceCreateUpdateSerializer,
    ADSerializer,
    InspectionTypeSerializer, InspectionTypeNestedSerializer,
    InspectionRecordNestedSerializer, InspectionRecordCreateUpdateSerializer,
)
from health.services import _end_of_month_after


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
                return Response(
                    AircraftNoteNestedSerializer(note, context={'request': request}).data,
                    status=status.HTTP_201_CREATED
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get', 'post'])
    def oil_records(self, request, pk=None):
        """
        Get or create oil records for an aircraft
        GET /api/aircraft/{id}/oil_records/ - Get all oil records
        POST /api/aircraft/{id}/oil_records/ - Create a new oil record
        """
        aircraft = self.get_object()

        if request.method == 'GET':
            records = aircraft.oil_records.all()
            return Response({
                'oil_records': OilRecordNestedSerializer(records, many=True).data,
            })

        elif request.method == 'POST':
            data = request.data.copy()
            data['aircraft'] = aircraft.id
            if 'flight_hours' not in data or not data['flight_hours']:
                data['flight_hours'] = str(aircraft.flight_time)

            serializer = OilRecordCreateSerializer(data=data)
            if serializer.is_valid():
                record = serializer.save()
                return Response(
                    OilRecordNestedSerializer(record).data,
                    status=status.HTTP_201_CREATED
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get', 'post'])
    def fuel_records(self, request, pk=None):
        """
        Get or create fuel records for an aircraft
        GET /api/aircraft/{id}/fuel_records/ - Get all fuel records
        POST /api/aircraft/{id}/fuel_records/ - Create a new fuel record
        """
        aircraft = self.get_object()

        if request.method == 'GET':
            records = aircraft.fuel_records.all()
            return Response({
                'fuel_records': FuelRecordNestedSerializer(records, many=True).data,
            })

        elif request.method == 'POST':
            data = request.data.copy()
            data['aircraft'] = aircraft.id
            if 'flight_hours' not in data or not data['flight_hours']:
                data['flight_hours'] = str(aircraft.flight_time)

            serializer = FuelRecordCreateSerializer(data=data)
            if serializer.is_valid():
                record = serializer.save()
                return Response(
                    FuelRecordNestedSerializer(record).data,
                    status=status.HTTP_201_CREATED
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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

                # Compute compliance status (worst of hours and calendar wins)
                if not compliance:
                    ad_dict['compliance_status'] = 'no_compliance'
                elif compliance.permanent:
                    ad_dict['compliance_status'] = 'compliant'
                else:
                    today = date_cls.today()
                    status_rank = 0  # 0=compliant, 1=due_soon, 2=overdue

                    # Check hours-based due
                    if compliance.next_due_at_time > 0:
                        if current_hours >= compliance.next_due_at_time:
                            status_rank = max(status_rank, 2)
                        elif current_hours + Decimal('10.0') >= compliance.next_due_at_time:
                            status_rank = max(status_rank, 1)

                    # Check calendar-based due (month recurrence)
                    if ad.recurring and ad.recurring_months > 0:
                        next_due_date = _end_of_month_after(compliance.date_complied, ad.recurring_months)
                        ad_dict['next_due_date'] = next_due_date.isoformat()
                        ad_dict['next_due_date_display'] = next_due_date.strftime('%B %Y')
                        if today > next_due_date:
                            status_rank = max(status_rank, 2)
                        elif today + td(days=30) >= next_due_date:
                            status_rank = max(status_rank, 1)

                    ad_dict['compliance_status'] = ['compliant', 'due_soon', 'overdue'][status_rank]

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
                return Response(ADNestedSerializer(ad).data, status=status.HTTP_200_OK)
            else:
                # Create a new AD and add to this aircraft
                serializer = ADSerializer(data=request.data, context={'request': request})
                if serializer.is_valid():
                    ad = serializer.save()
                    ad.applicable_aircraft.add(aircraft)
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

        serializer = ADComplianceCreateUpdateSerializer(data=data)
        if serializer.is_valid():
            record = serializer.save()
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

                # Compute compliance status
                if not last_record:
                    type_dict['compliance_status'] = 'never_completed'
                elif not insp_type.recurring:
                    type_dict['compliance_status'] = 'compliant'
                else:
                    status_rank = 0  # 0=compliant, 1=due_soon, 2=overdue
                    next_due_date = None

                    # Calendar-based check
                    if insp_type.recurring_months > 0 or insp_type.recurring_days > 0:
                        nd = last_record.date
                        if insp_type.recurring_months > 0:
                            nd = _end_of_month_after(nd, insp_type.recurring_months)
                        if insp_type.recurring_days > 0:
                            nd = nd + td(days=insp_type.recurring_days)
                        next_due_date = nd
                        if today > nd:
                            status_rank = max(status_rank, 2)
                        elif today + td(days=30) >= nd:
                            status_rank = max(status_rank, 1)

                    # Hours-based check
                    if insp_type.recurring_hours > 0:
                        recurring_hrs = Decimal(str(insp_type.recurring_hours))
                        hours_at = last_record.aircraft_hours
                        if hours_at is None and last_record.logbook_entry:
                            hours_at = last_record.logbook_entry.aircraft_hours_at_entry
                        if hours_at is not None:
                            hours_since = current_hours - hours_at
                            next_due_hours = hours_at + recurring_hrs
                            type_dict['next_due_hours'] = float(next_due_hours)
                            if hours_since >= recurring_hrs:
                                status_rank = max(status_rank, 2)
                            elif hours_since + Decimal('10.0') >= recurring_hrs:
                                status_rank = max(status_rank, 1)

                    if next_due_date:
                        type_dict['next_due_date'] = next_due_date.isoformat()

                    type_dict['compliance_status'] = ['compliant', 'due_soon', 'overdue'][status_rank]

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
                return Response(InspectionTypeNestedSerializer(insp_type).data, status=status.HTTP_200_OK)

            # Case 2: Create new InspectionType and add to aircraft
            if request.data.get('create_type'):
                create_data = {k: v for k, v in request.data.items() if k != 'create_type'}
                serializer = InspectionTypeSerializer(data=create_data, context={'request': request})
                if serializer.is_valid():
                    insp_type = serializer.save()
                    insp_type.applicable_aircraft.add(aircraft)
                    return Response(InspectionTypeNestedSerializer(insp_type).data, status=status.HTTP_201_CREATED)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            # Case 3: Create a new InspectionRecord for the aircraft
            data = request.data.copy()
            data['aircraft'] = aircraft.id

            serializer = InspectionRecordCreateUpdateSerializer(data=data)
            if serializer.is_valid():
                record = serializer.save()
                return Response(
                    InspectionRecordNestedSerializer(record).data,
                    status=status.HTTP_201_CREATED
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

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


class AircraftNoteViewSet(viewsets.ModelViewSet):
    queryset = AircraftNote.objects.all().order_by('-added_timestamp')
    serializer_class = AircraftNoteSerializer

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return AircraftNoteCreateUpdateSerializer
        return AircraftNoteNestedSerializer

    def perform_update(self, serializer):
        """Set edited_timestamp when note is updated"""
        serializer.save(edited_timestamp=timezone.now())


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
