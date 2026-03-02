import datetime
import uuid

import pytest
from django.db import IntegrityError, transaction

from core.models import Aircraft
from health.models import (
    AD,
    ADCompliance,
    Component,
    ComponentType,
    ConsumableRecord,
    Document,
    DocumentCollection,
    DocumentImage,
    FlightLog,
    ImportJob,
    InspectionRecord,
    InspectionType,
    LogbookEntry,
    MajorRepairAlteration,
    OilAnalysisReport,
    Squawk,
)

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# ComponentType
# ---------------------------------------------------------------------------

class TestComponentType:
    def test_name_unique_raises_on_duplicate(self, component_type):
        # component_type fixture already created 'Engine'
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ComponentType.objects.create(name='Engine')

    def test_str(self, component_type):
        assert str(component_type) == 'Engine'

    def test_uuid_pk_generated(self):
        ct = ComponentType.objects.create(name='Propeller')
        assert isinstance(ct.id, uuid.UUID)

    def test_consumable_default_false(self):
        ct = ComponentType.objects.create(name='Oil Filter')
        assert ct.consumable is False


# ---------------------------------------------------------------------------
# Component
# ---------------------------------------------------------------------------

class TestComponent:
    def test_status_default_spare(self, component_type):
        comp = Component.objects.create(
            component_type=component_type,
            manufacturer='Lycoming',
            model='O-360',
            date_in_service=datetime.date.today(),
        )
        assert comp.status == 'SPARE'

    def test_hours_in_service_default_zero(self, component_type):
        comp = Component.objects.create(
            component_type=component_type,
            manufacturer='Lycoming',
            model='O-360',
            date_in_service=datetime.date.today(),
        )
        assert float(comp.hours_in_service) == 0.0

    def test_hours_since_overhaul_default_zero(self, component_type):
        comp = Component.objects.create(
            component_type=component_type,
            manufacturer='Lycoming',
            model='O-360',
            date_in_service=datetime.date.today(),
        )
        assert float(comp.hours_since_overhaul) == 0.0

    def test_replacement_critical_default_false(self, component_type):
        comp = Component.objects.create(
            component_type=component_type,
            manufacturer='Lycoming',
            model='O-360',
            date_in_service=datetime.date.today(),
        )
        assert comp.replacement_critical is False

    def test_str_with_aircraft_and_location(self, aircraft, component_type):
        comp = Component.objects.create(
            aircraft=aircraft,
            component_type=component_type,
            manufacturer='Lycoming',
            model='O-360',
            install_location='Left Engine Bay',
            date_in_service=datetime.date.today(),
            status='IN-USE',
        )
        s = str(comp)
        assert 'Engine' in s
        assert 'N12345' in s
        assert 'Left Engine Bay' in s
        assert 'IN-USE' in s

    def test_str_without_aircraft(self, component_type):
        comp = Component.objects.create(
            component_type=component_type,
            manufacturer='Champion',
            model='Oil Filter',
            date_in_service=datetime.date.today(),
        )
        assert 'Engine' in str(comp)
        assert 'SPARE' in str(comp)

    def test_hours_to_tbo_with_tbo_set(self, component_type):
        comp = Component.objects.create(
            component_type=component_type,
            manufacturer='Lycoming',
            model='O-360',
            date_in_service=datetime.date.today(),
            tbo_hours=2000,
            hours_since_overhaul=350.0,
        )
        assert float(comp.hours_to_tbo()) == 1650.0

    def test_hours_to_tbo_no_tbo_returns_none(self, component_type):
        comp = Component.objects.create(
            component_type=component_type,
            manufacturer='Lycoming',
            model='O-360',
            date_in_service=datetime.date.today(),
            tbo_hours=None,
        )
        assert comp.hours_to_tbo() is None

    def test_is_due_for_service_tbo_critical(self, component_type):
        comp = Component.objects.create(
            component_type=component_type,
            manufacturer='Lycoming',
            model='O-360',
            date_in_service=datetime.date.today(),
            tbo_critical=True,
            inspection_critical=False,
            replacement_critical=False,
        )
        assert comp.is_due_for_service() is True

    def test_is_due_for_service_inspection_critical(self, component_type):
        comp = Component.objects.create(
            component_type=component_type,
            manufacturer='Lycoming',
            model='O-360',
            date_in_service=datetime.date.today(),
            tbo_critical=False,
            inspection_critical=True,
            replacement_critical=False,
        )
        assert comp.is_due_for_service() is True

    def test_is_due_for_service_replacement_critical(self, component_type):
        comp = Component.objects.create(
            component_type=component_type,
            manufacturer='Lycoming',
            model='O-360',
            date_in_service=datetime.date.today(),
            tbo_critical=False,
            inspection_critical=False,
            replacement_critical=True,
        )
        assert comp.is_due_for_service() is True

    def test_is_due_for_service_all_false(self, component_type):
        comp = Component.objects.create(
            component_type=component_type,
            manufacturer='Lycoming',
            model='O-360',
            date_in_service=datetime.date.today(),
            tbo_critical=False,
            inspection_critical=False,
            replacement_critical=False,
        )
        assert comp.is_due_for_service() is False

    def test_uuid_pk_generated(self, component_type):
        comp = Component.objects.create(
            component_type=component_type,
            manufacturer='Test',
            model='Widget',
            date_in_service=datetime.date.today(),
        )
        assert isinstance(comp.id, uuid.UUID)


# ---------------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------------

class TestDocument:
    def test_str_with_aircraft_and_collection(self, aircraft):
        coll = DocumentCollection.objects.create(aircraft=aircraft, name='Logbooks')
        doc = Document.objects.create(
            aircraft=aircraft,
            doc_type='LOG',
            name='Engine Logbook',
            collection=coll,
        )
        s = str(doc)
        assert 'N12345' in s
        assert 'LOG' in s
        assert 'Logbooks' in s

    def test_str_without_aircraft_or_collection(self):
        doc = Document.objects.create(doc_type='OTHER', name='Orphan Doc')
        s = str(doc)
        assert 'OTHER' in s

    def test_visibility_choices(self, aircraft):
        for vis in ('private', 'status', 'maintenance'):
            doc = Document.objects.create(
                aircraft=aircraft, doc_type='OTHER', name=f'doc-{vis}', visibility=vis
            )
            assert doc.visibility == vis

    def test_uuid_pk_generated(self, aircraft):
        doc = Document.objects.create(aircraft=aircraft, doc_type='OTHER', name='UUID test')
        assert isinstance(doc.id, uuid.UUID)


# ---------------------------------------------------------------------------
# DocumentCollection
# ---------------------------------------------------------------------------

class TestDocumentCollection:
    def test_starred_default_false(self, aircraft):
        coll = DocumentCollection.objects.create(aircraft=aircraft, name='My Docs')
        assert coll.starred is False

    def test_str(self, aircraft):
        coll = DocumentCollection.objects.create(aircraft=aircraft, name='Engine Records')
        assert 'N12345' in str(coll)
        assert 'Engine Records' in str(coll)

    def test_str_without_aircraft(self):
        coll = DocumentCollection.objects.create(name='Unattached Collection')
        assert 'Unattached Collection' in str(coll)

    def test_uuid_pk_generated(self, aircraft):
        coll = DocumentCollection.objects.create(aircraft=aircraft, name='UUID test')
        assert isinstance(coll.id, uuid.UUID)


# ---------------------------------------------------------------------------
# DocumentImage
# ---------------------------------------------------------------------------

class TestDocumentImage:
    def test_order_field_default_zero(self, aircraft):
        doc = Document.objects.create(aircraft=aircraft, doc_type='OTHER', name='Test Doc')
        image = DocumentImage.objects.create(document=doc, image='test/path/file.pdf')
        assert image.order == 0

    def test_str(self, aircraft):
        doc = Document.objects.create(aircraft=aircraft, doc_type='OTHER', name='Annual 2024')
        image = DocumentImage.objects.create(document=doc, image='test/path/file.pdf')
        assert 'Annual 2024' in str(image)

    def test_uuid_pk_generated(self, aircraft):
        doc = Document.objects.create(aircraft=aircraft, doc_type='OTHER', name='UUID Doc')
        image = DocumentImage.objects.create(document=doc, image='test/path/file.pdf')
        assert isinstance(image.id, uuid.UUID)


# ---------------------------------------------------------------------------
# LogbookEntry
# ---------------------------------------------------------------------------

class TestLogbookEntry:
    def test_log_type_default_ac(self, aircraft):
        entry = LogbookEntry.objects.create(
            aircraft=aircraft,
            date=datetime.date.today(),
            text='Test entry',
        )
        assert entry.log_type == 'AC'

    def test_entry_type_default_other(self, aircraft):
        entry = LogbookEntry.objects.create(
            aircraft=aircraft,
            date=datetime.date.today(),
            text='Default entry type',
        )
        assert entry.entry_type == 'OTHER'

    def test_component_hours_json_field_default_none(self, aircraft):
        entry = LogbookEntry.objects.create(
            aircraft=aircraft,
            date=datetime.date.today(),
            text='JSON default test',
        )
        # JSONField with null=True, blank=True — default is None (not set explicitly)
        assert entry.component_hours is None

    def test_str_with_aircraft(self, aircraft):
        entry = LogbookEntry.objects.create(
            aircraft=aircraft,
            date=datetime.date(2025, 6, 1),
            text='Oil change',
        )
        s = str(entry)
        assert 'N12345' in s
        assert 'AC' in s
        assert '2025-06-01' in s

    def test_str_without_aircraft(self):
        entry = LogbookEntry.objects.create(
            date=datetime.date(2025, 6, 1),
            text='No aircraft',
            log_type='ENG',
        )
        s = str(entry)
        assert 'ENG' in s

    def test_entry_type_choices_all_valid(self, aircraft):
        for et in ('FLIGHT', 'MAINTENANCE', 'INSPECTION', 'HOURS_UPDATE', 'OTHER'):
            entry = LogbookEntry.objects.create(
                aircraft=aircraft,
                date=datetime.date.today(),
                text=f'Entry {et}',
                entry_type=et,
            )
            assert entry.entry_type == et

    def test_uuid_pk_generated(self, aircraft):
        entry = LogbookEntry.objects.create(
            aircraft=aircraft, date=datetime.date.today(), text='UUID'
        )
        assert isinstance(entry.id, uuid.UUID)


# ---------------------------------------------------------------------------
# Squawk
# ---------------------------------------------------------------------------

class TestSquawk:
    def test_resolved_default_false(self, aircraft):
        sq = Squawk.objects.create(aircraft=aircraft, priority=1, issue_reported='Oil leak')
        assert sq.resolved is False

    def test_priority_choices_all_valid(self, aircraft):
        for priority in (0, 1, 2, 3):
            sq = Squawk.objects.create(
                aircraft=aircraft, priority=priority, issue_reported=f'Priority {priority}'
            )
            assert sq.priority == priority

    def test_str_with_aircraft(self, aircraft):
        sq = Squawk.objects.create(aircraft=aircraft, priority=2, issue_reported='Brake noise')
        s = str(sq)
        assert 'N12345' in s
        assert 'Brake noise' in s
        assert 'Resolved' in s

    def test_str_resolved_status_shown(self, aircraft):
        sq = Squawk.objects.create(aircraft=aircraft, priority=1, issue_reported='Fixed')
        sq.resolved = True
        sq.save()
        assert 'True' in str(sq)

    def test_uuid_pk_generated(self, aircraft):
        sq = Squawk.objects.create(aircraft=aircraft, priority=3, issue_reported='Minor')
        assert isinstance(sq.id, uuid.UUID)


# ---------------------------------------------------------------------------
# InspectionType
# ---------------------------------------------------------------------------

class TestInspectionType:
    def test_recurring_default_false(self):
        it = InspectionType.objects.create(name='One-Time Check')
        assert it.recurring is False

    def test_required_default_true(self):
        it = InspectionType.objects.create(name='Required Check')
        assert it.required is True

    def test_str(self, inspection_type):
        assert str(inspection_type) == 'Annual Inspection'

    def test_m2m_applicable_aircraft_works(self, aircraft):
        it = InspectionType.objects.create(name='ELT Check')
        it.applicable_aircraft.add(aircraft)
        assert aircraft in it.applicable_aircraft.all()

    def test_uuid_pk_generated(self):
        it = InspectionType.objects.create(name='UUID Inspection')
        assert isinstance(it.id, uuid.UUID)


# ---------------------------------------------------------------------------
# AD
# ---------------------------------------------------------------------------

class TestAD:
    def test_mandatory_default_true(self):
        a = AD.objects.create(name='AD 2021-05-01', short_description='Test')
        assert a.mandatory is True

    def test_compliance_type_default_standard(self):
        a = AD.objects.create(name='AD 2021-05-02', short_description='Test')
        assert a.compliance_type == 'standard'

    def test_str(self, ad):
        assert str(ad) == 'AD 2020-01-01'

    def test_m2m_applicable_aircraft_works(self, aircraft):
        a = AD.objects.create(name='AD 2022-01-01', short_description='Engine AD')
        a.applicable_aircraft.add(aircraft)
        assert aircraft in a.applicable_aircraft.all()

    def test_uuid_pk_generated(self):
        a = AD.objects.create(name='AD UUID-test', short_description='UUID test')
        assert isinstance(a.id, uuid.UUID)

    def test_compliance_type_conditional(self):
        a = AD.objects.create(
            name='AD 2021-05-03', short_description='Cond', compliance_type='conditional'
        )
        assert a.compliance_type == 'conditional'


# ---------------------------------------------------------------------------
# MajorRepairAlteration
# ---------------------------------------------------------------------------

class TestMajorRepairAlteration:
    def test_ordering_newest_date_first(self, aircraft):
        r1 = MajorRepairAlteration.objects.create(
            aircraft=aircraft,
            record_type='repair',
            title='Early repair',
            date_performed=datetime.date(2023, 1, 1),
        )
        r2 = MajorRepairAlteration.objects.create(
            aircraft=aircraft,
            record_type='alteration',
            title='Later alteration',
            date_performed=datetime.date(2024, 6, 15),
        )
        records = list(MajorRepairAlteration.objects.filter(aircraft=aircraft))
        assert records[0].id == r2.id
        assert records[1].id == r1.id

    def test_str_repair(self, aircraft):
        r = MajorRepairAlteration.objects.create(
            aircraft=aircraft,
            record_type='repair',
            title='Longeron repair',
            date_performed=datetime.date.today(),
        )
        s = str(r)
        assert 'Repair' in s
        assert 'Longeron repair' in s
        assert 'N12345' in s

    def test_str_alteration(self, aircraft):
        r = MajorRepairAlteration.objects.create(
            aircraft=aircraft,
            record_type='alteration',
            title='STC Installation',
            date_performed=datetime.date.today(),
        )
        assert 'Alteration' in str(r)

    def test_uuid_pk_generated(self, aircraft):
        r = MajorRepairAlteration.objects.create(
            aircraft=aircraft,
            record_type='repair',
            title='UUID test',
            date_performed=datetime.date.today(),
        )
        assert isinstance(r.id, uuid.UUID)


# ---------------------------------------------------------------------------
# InspectionRecord
# ---------------------------------------------------------------------------

class TestInspectionRecord:
    def test_create_minimal(self, aircraft, inspection_type):
        record = InspectionRecord.objects.create(
            inspection_type=inspection_type,
            aircraft=aircraft,
            date=datetime.date.today(),
        )
        assert record.pk is not None
        assert record.inspection_type == inspection_type
        assert record.aircraft == aircraft

    def test_create_with_aircraft_hours(self, aircraft, inspection_type):
        record = InspectionRecord.objects.create(
            inspection_type=inspection_type,
            aircraft=aircraft,
            date=datetime.date.today(),
            aircraft_hours=1250.5,
        )
        assert float(record.aircraft_hours) == 1250.5

    def test_str(self, aircraft, inspection_type):
        record = InspectionRecord.objects.create(
            inspection_type=inspection_type,
            aircraft=aircraft,
            date=datetime.date(2025, 3, 15),
        )
        s = str(record)
        assert 'Annual Inspection' in s
        assert 'N12345' in s
        assert '2025-03-15' in s

    def test_uuid_pk_generated(self, aircraft, inspection_type):
        record = InspectionRecord.objects.create(
            inspection_type=inspection_type,
            aircraft=aircraft,
            date=datetime.date.today(),
        )
        assert isinstance(record.id, uuid.UUID)


# ---------------------------------------------------------------------------
# ADCompliance
# ---------------------------------------------------------------------------

class TestADCompliance:
    def test_permanent_default_false(self, ad, aircraft):
        compliance = ADCompliance.objects.create(
            ad=ad,
            aircraft=aircraft,
            date_complied=datetime.date.today(),
            compliance_notes='Completed per AD',
        )
        assert compliance.permanent is False

    def test_create_minimal(self, ad, aircraft):
        compliance = ADCompliance.objects.create(
            ad=ad,
            aircraft=aircraft,
            date_complied=datetime.date.today(),
            compliance_notes='Done',
        )
        assert compliance.ad == ad
        assert compliance.aircraft == aircraft

    def test_str(self, ad, aircraft):
        compliance = ADCompliance.objects.create(
            ad=ad,
            aircraft=aircraft,
            date_complied=datetime.date(2025, 4, 1),
            compliance_notes='Complied',
        )
        s = str(compliance)
        assert 'AD 2020-01-01' in s
        assert 'N12345' in s
        assert '2025-04-01' in s

    def test_uuid_pk_generated(self, ad, aircraft):
        compliance = ADCompliance.objects.create(
            ad=ad,
            aircraft=aircraft,
            date_complied=datetime.date.today(),
            compliance_notes='UUID test',
        )
        assert isinstance(compliance.id, uuid.UUID)


# ---------------------------------------------------------------------------
# ImportJob
# ---------------------------------------------------------------------------

class TestImportJob:
    def test_status_default_pending(self, aircraft):
        job = ImportJob.objects.create(aircraft=aircraft)
        assert job.status == 'pending'

    def test_events_default_empty_list(self, aircraft):
        job = ImportJob.objects.create(aircraft=aircraft)
        assert job.events == []

    def test_str_with_aircraft(self, aircraft):
        job = ImportJob.objects.create(aircraft=aircraft)
        s = str(job)
        assert 'ImportJob' in s
        assert 'pending' in s
        assert 'N12345' in s

    def test_str_without_aircraft(self):
        job = ImportJob.objects.create(aircraft=None)
        s = str(job)
        assert 'ImportJob' in s
        assert 'pending' in s

    def test_job_type_choices(self, aircraft):
        for jt in ('logbook', 'oil_analysis', 'aircraft'):
            job = ImportJob.objects.create(aircraft=aircraft, job_type=jt)
            assert job.job_type == jt

    def test_uuid_pk_generated(self, aircraft):
        job = ImportJob.objects.create(aircraft=aircraft)
        assert isinstance(job.id, uuid.UUID)


# ---------------------------------------------------------------------------
# OilAnalysisReport
# ---------------------------------------------------------------------------

class TestOilAnalysisReport:
    def test_elements_ppm_json_default_empty_dict(self, aircraft):
        report = OilAnalysisReport.objects.create(
            aircraft=aircraft,
            sample_date=datetime.date.today(),
        )
        assert report.elements_ppm == {}

    def test_oil_properties_json_default_none(self, aircraft):
        report = OilAnalysisReport.objects.create(
            aircraft=aircraft,
            sample_date=datetime.date.today(),
        )
        assert report.oil_properties is None

    def test_ordering_newest_sample_date_first(self, aircraft):
        r1 = OilAnalysisReport.objects.create(
            aircraft=aircraft,
            sample_date=datetime.date(2024, 1, 1),
        )
        r2 = OilAnalysisReport.objects.create(
            aircraft=aircraft,
            sample_date=datetime.date(2025, 6, 1),
        )
        reports = list(OilAnalysisReport.objects.filter(aircraft=aircraft))
        assert reports[0].id == r2.id
        assert reports[1].id == r1.id

    def test_str(self, aircraft):
        report = OilAnalysisReport.objects.create(
            aircraft=aircraft,
            sample_date=datetime.date(2025, 5, 10),
        )
        s = str(report)
        assert 'N12345' in s
        assert 'Oil Analysis' in s
        assert '2025-05-10' in s

    def test_status_choices(self, aircraft):
        for st in ('normal', 'monitor', 'action_required'):
            report = OilAnalysisReport.objects.create(
                aircraft=aircraft,
                sample_date=datetime.date.today(),
                status=st,
            )
            assert report.status == st

    def test_uuid_pk_generated(self, aircraft):
        report = OilAnalysisReport.objects.create(
            aircraft=aircraft,
            sample_date=datetime.date.today(),
        )
        assert isinstance(report.id, uuid.UUID)


# ---------------------------------------------------------------------------
# FlightLog
# ---------------------------------------------------------------------------

class TestFlightLog:
    def test_ordering_newest_date_first(self, aircraft):
        fl1 = FlightLog.objects.create(
            aircraft=aircraft,
            date=datetime.date(2024, 3, 1),
            tach_time=1.5,
        )
        fl2 = FlightLog.objects.create(
            aircraft=aircraft,
            date=datetime.date(2025, 7, 15),
            tach_time=2.0,
        )
        logs = list(FlightLog.objects.filter(aircraft=aircraft))
        assert logs[0].id == fl2.id
        assert logs[1].id == fl1.id

    def test_str(self, aircraft):
        fl = FlightLog.objects.create(
            aircraft=aircraft,
            date=datetime.date(2025, 8, 1),
            tach_time=1.8,
        )
        s = str(fl)
        assert 'N12345' in s
        assert '1.8' in s
        assert '2025-08-01' in s

    def test_uuid_pk_generated(self, aircraft):
        fl = FlightLog.objects.create(
            aircraft=aircraft,
            date=datetime.date.today(),
            tach_time=1.0,
        )
        assert isinstance(fl.id, uuid.UUID)

    def test_hobbs_fields_optional(self, aircraft):
        fl = FlightLog.objects.create(
            aircraft=aircraft,
            date=datetime.date.today(),
            tach_time=1.2,
            hobbs_time=None,
            hobbs_out=None,
            hobbs_in=None,
        )
        assert fl.hobbs_time is None
        assert fl.hobbs_out is None
        assert fl.hobbs_in is None


# ---------------------------------------------------------------------------
# ConsumableRecord
# ---------------------------------------------------------------------------

class TestConsumableRecord:
    def test_record_type_oil(self, aircraft):
        record = ConsumableRecord.objects.create(
            record_type='oil',
            aircraft=aircraft,
            date=datetime.date.today(),
            quantity_added=2.0,
            flight_hours=100.0,
        )
        assert record.record_type == 'oil'

    def test_record_type_fuel(self, aircraft):
        record = ConsumableRecord.objects.create(
            record_type='fuel',
            aircraft=aircraft,
            date=datetime.date.today(),
            quantity_added=30.0,
            flight_hours=100.0,
        )
        assert record.record_type == 'fuel'

    def test_str_oil(self, aircraft):
        record = ConsumableRecord.objects.create(
            record_type='oil',
            aircraft=aircraft,
            date=datetime.date(2025, 5, 1),
            quantity_added=2.0,
            flight_hours=150.0,
        )
        s = str(record)
        assert 'N12345' in s
        assert 'Oil' in s
        assert '2.00' in s or '2.0' in s
        assert '150' in s

    def test_str_fuel(self, aircraft):
        record = ConsumableRecord.objects.create(
            record_type='fuel',
            aircraft=aircraft,
            date=datetime.date(2025, 5, 1),
            quantity_added=40.0,
            flight_hours=150.0,
        )
        s = str(record)
        assert 'N12345' in s
        assert 'Fuel' in s

    def test_uuid_pk_generated(self, aircraft):
        record = ConsumableRecord.objects.create(
            record_type='oil',
            aircraft=aircraft,
            date=datetime.date.today(),
            quantity_added=1.0,
            flight_hours=100.0,
        )
        assert isinstance(record.id, uuid.UUID)
