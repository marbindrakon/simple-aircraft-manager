"""Public (unauthenticated) API views for shared aircraft links."""
import re
from datetime import date as date_cls

from django.db.models import Q
from django.http import JsonResponse
from django.views import View

from rest_framework.parsers import JSONParser
from rest_framework.request import Request

from core.models import AircraftShareToken
from core.serializers import AircraftSerializer, AircraftNoteNestedSerializer
from core.sharing import validate_share_token
from health.models import (
    Component, LogbookEntry, Squawk, Document, DocumentCollection,
    ConsumableRecord, AD, ADCompliance, InspectionType, InspectionRecord,
    MajorRepairAlteration, OilAnalysisReport,
)
from health.serializers import (
    ComponentSerializer,
    LogbookEntrySerializer,
    SquawkNestedSerializer,
    DocumentCollectionNestedSerializer, DocumentNestedSerializer,
    ConsumableRecordNestedSerializer,
    ADNestedSerializer, ADComplianceNestedSerializer,
    InspectionTypeNestedSerializer, InspectionRecordNestedSerializer,
    MajorRepairAlterationNestedSerializer,
    OilAnalysisReportSerializer,
)
from health.services import ad_compliance_status, inspection_compliance_status, STATUS_LABELS


class PublicAircraftSummaryAPI(View):
    """Public API endpoint that returns aircraft summary data for shared links."""

    def get(self, request, share_token):
        token_obj, error = validate_share_token(share_token)
        if error:
            return error
        aircraft = token_obj.aircraft
        privilege = token_obj.privilege

        drf_request = Request(request, parsers=[JSONParser()])

        current_hours = aircraft.tach_time - aircraft.tach_time_offset
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
        token_obj, error = validate_share_token(share_token)
        if error:
            return error
        if token_obj.privilege == 'status':
            return JsonResponse({'error': 'Not found'}, status=404)
        aircraft = token_obj.aircraft

        try:
            limit = min(int(request.GET.get('limit', 50)), 200)
            offset = max(int(request.GET.get('offset', 0)), 0)
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Invalid pagination parameters'}, status=400)

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
