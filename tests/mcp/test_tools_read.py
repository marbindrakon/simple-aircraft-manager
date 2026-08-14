"""Read tools: content, filtering, RBAC scoping, feature gating."""
import datetime

import pytest

from core.models import AircraftFeature
from health.models import ConsumableRecord, Squawk

from .conftest import tool_error, tool_payload

pytestmark = pytest.mark.urls('tests.mcp.urls')


class TestListAircraft:
    def test_owner_sees_own_aircraft(self, owner_mcp_client, aircraft):
        payload = tool_payload(owner_mcp_client, 'list_aircraft')
        assert payload['count'] == 1
        entry = payload['aircraft'][0]
        assert entry['tail_number'] == 'N12345'
        assert entry['airworthiness']['status'] in ('RED', 'ORANGE', 'GREEN')

    def test_other_user_sees_nothing(self, other_mcp_client, aircraft):
        payload = tool_payload(other_mcp_client, 'list_aircraft')
        assert payload['count'] == 0

    def test_admin_sees_all(self, mcp_client_factory, admin_user, aircraft):
        client = mcp_client_factory(admin_user)
        assert tool_payload(client, 'list_aircraft')['count'] == 1


class TestAircraftSummary:
    def test_summary_contents(self, owner_mcp_client, aircraft, component, squawk, logbook_entry):
        payload = tool_payload(owner_mcp_client, 'get_aircraft_summary',
                               {'aircraft_id': str(aircraft.id)})
        assert payload['aircraft']['tail_number'] == 'N12345'
        assert 'airworthiness' in payload['aircraft']
        assert len(payload['components']) == 1
        assert len(payload['recent_logs']) == 1
        assert len(payload['active_squawks']) == 1
        assert 'features' in payload

    def test_pilot_can_read(self, pilot_mcp_client, aircraft_with_pilot):
        payload = tool_payload(pilot_mcp_client, 'get_aircraft_summary',
                               {'aircraft_id': str(aircraft_with_pilot.id)})
        assert payload['aircraft']['tail_number'] == 'N12345'

    def test_no_role_gets_not_found(self, other_mcp_client, aircraft):
        message = tool_error(other_mcp_client, 'get_aircraft_summary',
                             {'aircraft_id': str(aircraft.id)})
        assert message == 'Aircraft not found'

    def test_unknown_id_same_error_as_no_role(self, other_mcp_client, aircraft):
        bogus = tool_error(other_mcp_client, 'get_aircraft_summary',
                           {'aircraft_id': '00000000-0000-0000-0000-000000000000'})
        no_role = tool_error(other_mcp_client, 'get_aircraft_summary',
                             {'aircraft_id': str(aircraft.id)})
        assert bogus == no_role  # enumeration-safe

    def test_malformed_id(self, owner_mcp_client):
        assert tool_error(owner_mcp_client, 'get_aircraft_summary',
                          {'aircraft_id': 'not-a-uuid'}) == 'Aircraft not found'


class TestAirworthinessAndCompliance:
    def test_green_aircraft(self, owner_mcp_client, aircraft):
        payload = tool_payload(owner_mcp_client, 'get_airworthiness',
                               {'aircraft_id': str(aircraft.id)})
        assert payload['status'] == 'GREEN'
        assert payload['can_fly'] is True

    def test_grounding_squawk_goes_red(self, owner_mcp_client, aircraft):
        Squawk.objects.create(aircraft=aircraft, priority=0, issue_reported='Engine fire')
        payload = tool_payload(owner_mcp_client, 'get_airworthiness',
                               {'aircraft_id': str(aircraft.id)})
        assert payload['status'] == 'RED'
        assert payload['can_fly'] is False
        assert any(i['category'] == 'SQUAWK' for i in payload['issues'])

    def test_compliance_status_sections(self, owner_mcp_client, aircraft, ad, inspection_type):
        payload = tool_payload(owner_mcp_client, 'get_compliance_status',
                               {'aircraft_id': str(aircraft.id)})
        assert payload['ads'][0]['compliance_status'] == 'no_compliance'
        assert payload['inspections'][0]['compliance_status'] == 'never_completed'

    def test_compliance_include_filter(self, owner_mcp_client, aircraft, ad, inspection_type):
        payload = tool_payload(owner_mcp_client, 'get_compliance_status',
                               {'aircraft_id': str(aircraft.id), 'include': ['ads']})
        assert 'ads' in payload
        assert 'inspections' not in payload


class TestSquawksEventsLogbook:
    def test_list_squawks_filter(self, owner_mcp_client, aircraft, squawk):
        Squawk.objects.create(aircraft=aircraft, priority=2,
                              issue_reported='Fixed thing', resolved=True)
        all_payload = tool_payload(owner_mcp_client, 'list_squawks',
                                   {'aircraft_id': str(aircraft.id)})
        assert all_payload['count'] == 2
        open_payload = tool_payload(owner_mcp_client, 'list_squawks',
                                    {'aircraft_id': str(aircraft.id), 'resolved': False})
        assert open_payload['count'] == 1
        assert open_payload['squawks'][0]['issue_reported'] == 'Brake squeak'

    def test_get_events(self, owner_mcp_client, aircraft):
        from core.events import log_event
        log_event(aircraft, 'hours', 'Hours updated to 101')
        log_event(aircraft, 'note', 'Note added')
        payload = tool_payload(owner_mcp_client, 'get_events',
                               {'aircraft_id': str(aircraft.id), 'category': 'hours'})
        assert payload['total'] == 1
        assert payload['events'][0]['event_name'] == 'Hours updated to 101'

    def test_get_events_bad_category(self, owner_mcp_client, aircraft):
        message = tool_error(owner_mcp_client, 'get_events',
                             {'aircraft_id': str(aircraft.id), 'category': 'bogus'})
        assert 'Invalid category' in message

    def test_search_logbook(self, owner_mcp_client, aircraft, logbook_entry):
        payload = tool_payload(owner_mcp_client, 'search_logbook',
                               {'aircraft_id': str(aircraft.id), 'query': '100-hour'})
        assert payload['total'] == 1
        miss = tool_payload(owner_mcp_client, 'search_logbook',
                            {'aircraft_id': str(aircraft.id), 'query': 'propeller strike'})
        assert miss['total'] == 0

    def test_search_logbook_date_range(self, owner_mcp_client, aircraft, logbook_entry):
        today = datetime.date.today().isoformat()
        payload = tool_payload(owner_mcp_client, 'search_logbook',
                               {'aircraft_id': str(aircraft.id),
                                'date_from': today, 'date_to': today})
        assert payload['total'] == 1
        message = tool_error(owner_mcp_client, 'search_logbook',
                             {'aircraft_id': str(aircraft.id), 'date_from': 'nope'})
        assert 'ISO date' in message


class TestConsumptionStats:
    def _record(self, aircraft, hours, qty, excluded=False):
        return ConsumableRecord.objects.create(
            aircraft=aircraft,
            record_type='oil',
            date=datetime.date.today(),
            quantity_added=qty,
            flight_hours=hours,
            excluded_from_averages=excluded,
        )

    def test_oil_hours_per_quart(self, owner_mcp_client, aircraft):
        # Two intervals of 10 hours per 1 quart each
        self._record(aircraft, 100, 1)
        self._record(aircraft, 110, 1)
        self._record(aircraft, 120, 1)
        payload = tool_payload(owner_mcp_client, 'get_consumption_stats',
                               {'aircraft_id': str(aircraft.id), 'type': 'oil'})
        assert payload['metric'] == 'hours_per_quart'
        assert payload['average'] == 10.0
        assert payload['interval_count'] == 2

    def test_excluded_records_skipped(self, owner_mcp_client, aircraft):
        self._record(aircraft, 100, 1)
        self._record(aircraft, 110, 1)
        self._record(aircraft, 111, 1, excluded=True)  # 1 hr/qt outlier, excluded
        payload = tool_payload(owner_mcp_client, 'get_consumption_stats',
                               {'aircraft_id': str(aircraft.id), 'type': 'oil'})
        assert payload['average'] == 10.0
        assert payload['excluded_from_average'] == 1

    def test_feature_disabled(self, owner_mcp_client, aircraft):
        AircraftFeature.objects.create(aircraft=aircraft, feature='oil_consumption', enabled=False)
        message = tool_error(owner_mcp_client, 'get_consumption_stats',
                             {'aircraft_id': str(aircraft.id), 'type': 'oil'})
        assert 'disabled' in message

    def test_no_records(self, owner_mcp_client, aircraft):
        payload = tool_payload(owner_mcp_client, 'get_consumption_stats',
                               {'aircraft_id': str(aircraft.id), 'type': 'fuel'})
        assert payload['average'] is None
        assert payload['record_count'] == 0


class TestLogbookSlimAndPagination:
    def _make_entries(self, aircraft, n, with_doc=False):
        import datetime as dt
        from health.models import Document, DocumentImage, LogbookEntry
        doc = None
        if with_doc:
            doc = Document.objects.create(aircraft=aircraft, name='Engine Log 1', doc_type='LOG')
            for i in range(3):
                DocumentImage.objects.create(document=doc, image=f'imgs/p{i}.png', order=i)
        entries = []
        for i in range(n):
            entries.append(LogbookEntry.objects.create(
                aircraft=aircraft,
                date=dt.date(2026, 1, 1) + dt.timedelta(days=i),
                log_type='ENG',
                entry_type='MAINTENANCE',
                text=f'Entry {i}',
                log_image=doc,
                page_number=i + 1,
            ))
        return entries

    def test_entries_are_slim_with_document_reference(self, owner_mcp_client, aircraft):
        self._make_entries(aircraft, 2, with_doc=True)
        payload = tool_payload(owner_mcp_client, 'search_logbook',
                               {'aircraft_id': str(aircraft.id)})
        entry = payload['entries'][0]
        # Heavy manifest fields must be gone
        for heavy in ('log_image_detail', 'related_documents_detail', 'url', 'log_image'):
            assert heavy not in entry
        # Compact reference remains
        assert entry['log_document']['name'] == 'Engine Log 1'
        assert 'id' in entry['log_document']
        assert entry['page_number'] == 2
        assert entry['related_documents'] == []

    def test_summary_recent_logs_are_slim(self, owner_mcp_client, aircraft):
        self._make_entries(aircraft, 1, with_doc=True)
        payload = tool_payload(owner_mcp_client, 'get_aircraft_summary',
                               {'aircraft_id': str(aircraft.id)})
        entry = payload['recent_logs'][0]
        assert 'log_image_detail' not in entry
        assert entry['log_document']['name'] == 'Engine Log 1'

    def test_offset_pagination_walks_without_duplicates(self, owner_mcp_client, aircraft):
        self._make_entries(aircraft, 7)
        seen = []
        offset = 0
        while True:
            page = tool_payload(owner_mcp_client, 'search_logbook', {
                'aircraft_id': str(aircraft.id), 'limit': 3, 'offset': offset,
            })
            assert page['offset'] == offset
            seen.extend(e['id'] for e in page['entries'])
            if offset + 3 >= page['total']:
                break
            offset += 3
        assert len(seen) == 7
        assert len(set(seen)) == 7  # no boundary duplicates


class TestSummaryRegression:
    def test_summary_with_attributed_squawk_and_flight_log(self, owner_mcp_client, aircraft, owner_user):
        """R1 regression: once Squawk.reported_by is populated, AircraftSerializer's
        depth=1 nested a Squawk whose User FK hyperlinked to the nonexistent
        'user-detail' route and 500'd. Reverse relations must serialize as PK lists."""
        import datetime as dt
        from health.models import FlightLog
        Squawk.objects.create(
            aircraft=aircraft, priority=3, issue_reported='Seat rail wear',
            reported_by=owner_user)
        FlightLog.objects.create(
            aircraft=aircraft, date=dt.date.today(), tach_time=1)
        payload = tool_payload(owner_mcp_client, 'get_aircraft_summary',
                               {'aircraft_id': str(aircraft.id)})
        # Reverse relations on the aircraft object are compacted to counts
        assert payload['aircraft']['squawks_count'] == 1
        assert payload['aircraft']['flight_logs_count'] == 1
        # The hydrated squawk list is still served at the top level
        assert payload['active_squawks'][0]['issue_reported'] == 'Seat rail wear'

    def test_summary_is_context_friendly(self, owner_mcp_client, aircraft, component):
        payload = tool_payload(owner_mcp_client, 'get_aircraft_summary',
                               {'aircraft_id': str(aircraft.id)})
        # No bare UUID lists or URLs on the aircraft object
        assert 'url' not in payload['aircraft']
        assert not any(isinstance(v, list) for v in payload['aircraft'].values())
        assert payload['aircraft']['components_count'] == 1
        # Airworthiness detail survives compaction
        assert 'issues' in payload['aircraft']['airworthiness']
        # Components keep scalars/hours/criticality, lose hyperlink relations
        comp = payload['components'][0]
        assert comp['component_type_name'] == 'Engine'
        assert 'hours_in_service' in comp and 'tbo_critical' in comp
        for dropped in ('aircraft', 'component_type', 'documents', 'ads', 'inspections'):
            assert dropped not in comp
        # Static catalog omitted; live feature map kept
        assert 'feature_catalog' not in payload
        assert 'features' in payload
