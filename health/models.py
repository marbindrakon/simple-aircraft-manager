from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models

from core import models as core_models
from core.models import make_upload_path

import uuid

# Create your models here.

LOG_TYPES = (
        ('ENG', 'Engine'),
        ('AC', 'Aircraft'),
        ('PROP', 'Propeller'),
        ('OTHER', 'Other'),
)

SQUAWK_PRIORITIES = (
        (0, "Ground Aircraft"),
        (1, "Fix Soon"),
        (2, "Fix at Next Inspection"),
        (3, "Fix Eventually"),
)

DOCUMENT_TYPES = (
        ('LOG', 'Logbook'),
        ('ALTER', 'Alteration Record'),
        ('REPORT', 'Report'),
        ('ESTIMATE', 'Estimate'),
        ('DISC', 'Discrepancy List'),
        ('INVOICE', 'Receipt / Invoice'),
        ('AIRCRAFT', 'Aircraft Record'),
        ('OTHER', 'Other'),
)

DOCUMENT_VISIBILITY_CHOICES = [
    ('private', 'Private'),
    ('status', 'All share links'),
    ('maintenance', 'Maintenance only'),
]

COMPONENT_STATUSES = (
        ('SPARE', 'Spare Part'),
        ('IN-USE', 'In Service'),
        ('DISPOSED', 'Disposed'),
)

# Aliases retained for existing migrations that reference them by name
random_document_filename = make_upload_path("health/documents")
random_squawk_filename = make_upload_path("health/squawks")

class ComponentType(models.Model):
    id = models.UUIDField(primary_key=True, blank=False, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=254, unique=True)
    consumable = models.BooleanField(default=False)

    def __str__(self):
        return self.name

class Component(models.Model):
    id = models.UUIDField(primary_key=True, blank=False, default=uuid.uuid4, editable=False)
    aircraft = models.ForeignKey(core_models.Aircraft, related_name='components', on_delete=models.CASCADE, blank=True, null=True)
    parent_component = models.ForeignKey('self', related_name='components', blank=True, null=True, on_delete=models.CASCADE)
    component_type = models.ForeignKey(ComponentType, on_delete=models.CASCADE)
    manufacturer = models.CharField(max_length=254)
    model = models.CharField(max_length=254)
    serial_number = models.CharField(max_length=254, blank=True)
    install_location = models.CharField(max_length=254, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=254, choices=COMPONENT_STATUSES, default='SPARE')
    date_in_service = models.DateField()
    hours_in_service = models.DecimalField(max_digits=8, decimal_places=1, default=0.0)
    hours_since_overhaul = models.DecimalField(max_digits=8, decimal_places=1, default=0.0)
    overhaul_date = models.DateField(blank=True, null=True)
    tbo_hours = models.IntegerField(blank=True, null=True)
    tbo_days = models.IntegerField(blank=True, null=True)
    inspection_hours = models.IntegerField(blank=True, null=True)
    inspection_days = models.IntegerField(blank=True, null=True)
    replacement_hours = models.IntegerField(blank=True, null=True)
    replacement_days = models.IntegerField(blank=True, null=True)
    tbo_critical = models.BooleanField(default=True)
    on_condition = models.BooleanField(default=False)
    inspection_critical = models.BooleanField(default=True)
    replacement_critical = models.BooleanField(default=False)

    def __str__(self):
        ret_string = f"{self.component_type.name}"
        if self.aircraft:
            ret_string += f" - {self.aircraft.tail_number}"
        if self.install_location:
            ret_string += f" - {self.install_location}"
        ret_string += f" - {self.status}"
        return ret_string

    def hours_to_tbo(self):
        """Hours remaining until TBO"""
        if self.tbo_hours:
            return self.tbo_hours - self.hours_since_overhaul
        return None

    def is_due_for_service(self):
        """Check if component needs service"""
        return any([
            self.tbo_critical,
            self.inspection_critical,
            self.replacement_critical
        ])

class DocumentCollection(models.Model):
    id = models.UUIDField(primary_key=True, blank=False, default=uuid.uuid4, editable=False)
    aircraft = models.ForeignKey(core_models.Aircraft, related_name='doc_collections', on_delete=models.CASCADE, blank=True, null=True)
    components = models.ManyToManyField(Component, related_name='doc_collections', blank=True)
    name = models.CharField(max_length=254)
    description = models.TextField(blank=True)
    visibility = models.CharField(max_length=20, choices=DOCUMENT_VISIBILITY_CHOICES, default='private')
    starred = models.BooleanField(default=False)

    def __str__(self):
        ret_string = ""
        if self.aircraft:
            ret_string += f"{self.aircraft.tail_number}"
        ret_string += f" - {self.name}"
        return ret_string


class Document(models.Model):
    id = models.UUIDField(primary_key=True, blank=False, default=uuid.uuid4, editable=False)
    aircraft = models.ForeignKey(core_models.Aircraft, related_name='documents', on_delete=models.CASCADE, blank=True, null=True)
    components = models.ManyToManyField(Component, related_name='documents', blank=True)
    doc_type = models.CharField(max_length=254, choices=DOCUMENT_TYPES, default='OTHER')
    collection = models.ForeignKey(DocumentCollection, related_name='documents', on_delete=models.CASCADE, blank=True, null=True)
    name = models.CharField(max_length=254)
    description = models.TextField(blank=True)
    visibility = models.CharField(max_length=20, choices=DOCUMENT_VISIBILITY_CHOICES, null=True, blank=True, default=None)

    def __str__(self):
        ret_string = ""
        if self.aircraft:
            ret_string += f"{self.aircraft.tail_number}"
        ret_string += f" - {self.doc_type}"
        if self.collection:
            ret_string += f" - {self.collection.name}"
        return ret_string

class DocumentImage(models.Model):
    id = models.UUIDField(primary_key=True, blank=False, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, related_name='images', on_delete=models.CASCADE)
    notes = models.TextField(blank=True)
    image = models.FileField(
        upload_to=random_document_filename,
        validators=[FileExtensionValidator(
            allowed_extensions=['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'tiff', 'pdf', 'txt']
        )],
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        ret_string = "Doc Image"
        ret_string += f" - {self.document.name}"
        return ret_string

class LogbookEntry(models.Model):
    id = models.UUIDField(primary_key=True, blank=False, default=uuid.uuid4, editable=False)
    log_type = models.CharField(max_length=254, choices=LOG_TYPES, default='AC')
    aircraft = models.ForeignKey(core_models.Aircraft, related_name='logbook_entries', on_delete=models.CASCADE, blank=True, null=True)
    component = models.ManyToManyField(Component, related_name='logbook_entries', blank=True)
    date = models.DateField()
    text = models.TextField()
    signoff_person = models.TextField(blank=True)
    signoff_location = models.CharField(max_length=254, blank=True)
    log_image = models.ForeignKey(Document, related_name='log_entry', blank=True, null=True, on_delete=models.SET_NULL)
    related_documents = models.ManyToManyField(Document, related_name='related_logs', blank=True)

    # Hours tracking fields
    aircraft_hours_at_entry = models.DecimalField(
        max_digits=8, decimal_places=1, blank=True, null=True,
        help_text="Aircraft total hours at time of entry"
    )
    component_hours = models.JSONField(
        blank=True, null=True,
        help_text="Snapshot of component hours {component_id: hours}"
    )
    entry_type = models.CharField(
        max_length=50,
        choices=[
            ('FLIGHT', 'Flight'),
            ('MAINTENANCE', 'Maintenance'),
            ('INSPECTION', 'Inspection'),
            ('HOURS_UPDATE', 'Hours Update'),
            ('OTHER', 'Other'),
        ],
        default='OTHER'
    )
    page_number = models.PositiveIntegerField(
        blank=True, null=True,
        help_text="1-based page number within the attached log_image document"
    )

    def __str__(self):
        ret_string = ""
        if self.aircraft:
            ret_string += f"{self.aircraft.tail_number}"
        ret_string += f" - {self.log_type}"
        ret_string += f" - {self.date}"
        return ret_string

class Squawk(models.Model):
    id = models.UUIDField(primary_key=True, blank=False, default=uuid.uuid4, editable=False)
    aircraft = models.ForeignKey(core_models.Aircraft, related_name='squawks', on_delete=models.CASCADE, blank=True, null=True)
    component = models.ForeignKey(Component, related_name='squawks', blank=True, null=True, on_delete=models.SET_NULL)
    priority = models.IntegerField(choices=SQUAWK_PRIORITIES, default=0)
    issue_reported = models.TextField(blank=True)
    attachment = models.FileField(upload_to=random_squawk_filename, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='reported_squawks', blank=True, null=True, on_delete=models.SET_NULL)
    resolved = models.BooleanField(default=False)
    logbook_entries = models.ManyToManyField(LogbookEntry, blank=True, related_name='squawks')
    notes = models.TextField(blank=True)

    def __str__(self):
        ret_string = ""
        if self.aircraft:
            ret_string += f"{self.aircraft.tail_number}"
        if self.component:
            ret_string += f"{self.component.component_type}"
        ret_string += f" - {self.issue_reported}"
        ret_string += f" - Resolved: {self.resolved}"
        return ret_string

class InspectionType(models.Model):
    id = models.UUIDField(primary_key=True, blank=False, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=254)
    recurring = models.BooleanField(default=False)
    required = models.BooleanField(default=True)
    recurring_hours = models.DecimalField(max_digits=8, decimal_places=1, default=0.0)
    recurring_days = models.IntegerField(default=0)
    recurring_months = models.IntegerField(default=0)
    applicable_aircraft = models.ManyToManyField(core_models.Aircraft, related_name='applicable_inspections', blank=True)
    applicable_component = models.ManyToManyField(Component, related_name='applicable_inspections', blank=True)

    def __str__(self):
        return self.name

COMPLIANCE_TYPES = (
    ('standard', 'Standard'),
    ('conditional', 'Conditional'),
)

BULLETIN_TYPE_CHOICES = [
    ('ad',    'Airworthiness Directive'),
    ('saib',  'Special Airworthiness Information Bulletin'),
    ('sb',    'Service Bulletin'),
    ('alert', 'Airworthiness Alert'),
    ('other', 'Other'),
]

class AD(models.Model):
    id = models.UUIDField(primary_key=True, blank=False, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=254)
    short_description = models.CharField(max_length=254)
    required_action = models.TextField(blank=True)
    compliance_type = models.CharField(max_length=20, choices=COMPLIANCE_TYPES, default='standard')
    trigger_condition = models.TextField(blank=True)
    recurring = models.BooleanField(default=False)
    recurring_hours = models.DecimalField(max_digits=8, decimal_places=1, default=0.0)
    recurring_months = models.IntegerField(default=0)
    recurring_days = models.IntegerField(default=0)
    bulletin_type = models.CharField(max_length=20, choices=BULLETIN_TYPE_CHOICES, default='ad')
    mandatory = models.BooleanField(default=True)
    document = models.ForeignKey(
        'Document',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='referenced_by_ads',
        help_text="Optional reference to a document (e.g., copy of the bulletin)"
    )
    on_inspection_type = models.ManyToManyField(InspectionType, blank=True)
    applicable_aircraft = models.ManyToManyField(core_models.Aircraft, related_name='ads', blank=True)
    applicable_component = models.ManyToManyField(Component, related_name='ads', blank=True)

    def __str__(self):
        return self.name

MAJOR_RECORD_TYPES = (
    ('repair', 'Major Repair'),
    ('alteration', 'Major Alteration'),
)

class MajorRepairAlteration(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    aircraft = models.ForeignKey(core_models.Aircraft, related_name='major_records', on_delete=models.CASCADE)
    record_type = models.CharField(max_length=20, choices=MAJOR_RECORD_TYPES)

    # Description
    title = models.CharField(max_length=254, help_text="Brief title, e.g. 'Longeron repair' or 'STC SA00001SE installation'")
    description = models.TextField(blank=True, help_text="Detailed description of the work performed")
    date_performed = models.DateField(help_text="Date the repair or alteration was completed")
    performed_by = models.CharField(max_length=254, blank=True, help_text="Mechanic, shop, or IA who performed the work")

    # What was worked on
    component = models.ForeignKey(Component, related_name='major_records', blank=True, null=True, on_delete=models.SET_NULL,
                                  help_text="Component this applies to (engine, prop, etc.), if applicable")

    # Form 337 document
    form_337_document = models.ForeignKey(Document, related_name='form_337_records', blank=True, null=True, on_delete=models.SET_NULL,
                                          help_text="Scanned/uploaded Form 337 document")

    # STC info (alterations only, optional)
    stc_number = models.CharField(max_length=100, blank=True, help_text="STC number (e.g. SA00001SE), if this alteration was done under an STC")
    stc_holder = models.CharField(max_length=254, blank=True, help_text="STC holder / manufacturer name")
    stc_document = models.ForeignKey(Document, related_name='stc_records', blank=True, null=True, on_delete=models.SET_NULL,
                                     help_text="STC paperwork / data package document")

    # Linkages
    logbook_entry = models.ForeignKey(LogbookEntry, related_name='major_records', blank=True, null=True, on_delete=models.SET_NULL,
                                      help_text="Associated logbook entry recording this work")
    aircraft_hours = models.DecimalField(max_digits=8, decimal_places=1, blank=True, null=True,
                                         help_text="Aircraft total hours at time of work")

    # Instructions for Continued Airworthiness (ICAs)
    has_ica = models.BooleanField(default=False, help_text="This record includes Instructions for Continued Airworthiness (ICAs)")
    ica_notes = models.TextField(blank=True, help_text="Notes about where the ICAs are located and what they cover")

    # Metadata
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_performed', '-created_at']

    def __str__(self):
        prefix = "Repair" if self.record_type == 'repair' else "Alteration"
        tail = self.aircraft.tail_number if self.aircraft else "?"
        return f"{prefix}: {self.title} ({tail})"

class InspectionRecord(models.Model):
    id = models.UUIDField(primary_key=True, blank=False, default=uuid.uuid4, editable=False)
    date = models.DateField()
    aircraft_hours = models.DecimalField(
        max_digits=8, decimal_places=1, blank=True, null=True,
        help_text="Aircraft total hours at time of inspection"
    )
    inspection_type = models.ForeignKey(InspectionType, on_delete=models.CASCADE)
    logbook_entry = models.ForeignKey(LogbookEntry, related_name='inspections', blank=True, null=True, on_delete=models.CASCADE)
    documents = models.ManyToManyField(Document, related_name='inspections', blank=True)
    aircraft = models.ForeignKey(core_models.Aircraft, related_name='inspections', on_delete=models.CASCADE, blank=True, null=True)
    component = models.ManyToManyField(Component, related_name='inspections', blank=True)

    def __str__(self):
        ret_string = f"{self.inspection_type}"
        if self.aircraft:
            ret_string += f" - {self.aircraft.tail_number}"
        ret_string += f" - {self.date}"
        return ret_string

class ADCompliance(models.Model):
    id = models.UUIDField(primary_key=True, blank=False, default=uuid.uuid4, editable=False)
    ad = models.ForeignKey(AD, on_delete=models.CASCADE)
    date_complied = models.DateField()
    compliance_notes = models.TextField()
    permanent = models.BooleanField(default=False)
    next_due_at_time = models.DecimalField(max_digits=8, decimal_places=1, default=0.0)
    aircraft_hours_at_compliance = models.DecimalField(max_digits=8, decimal_places=1, blank=True, null=True)
    logbook_entry = models.ForeignKey(LogbookEntry, related_name='ads_complied', blank=True, null=True, on_delete=models.CASCADE)
    inspection_record = models.ForeignKey(InspectionRecord, related_name='ads_complied', blank=True, null=True, on_delete=models.CASCADE)
    aircraft = models.ForeignKey(core_models.Aircraft, related_name='ad_compliance', blank=True, null=True, on_delete=models.CASCADE)
    component = models.ForeignKey(Component, related_name='ad_compliance', blank=True, null=True, on_delete=models.CASCADE)

    def __str__(self):
        ret_string = f"{self.ad.name}"
        if self.aircraft:
            ret_string += f" - {self.aircraft.tail_number}"
        if self.component:
            ret_string += f"{self.component.component_type}"
        ret_string += f" - {self.date_complied}"
        return ret_string


class ImportJob(models.Model):
    """Track background import jobs (logbook or aircraft)."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # aircraft is null for aircraft-import jobs until the import completes
    aircraft = models.ForeignKey(core_models.Aircraft, on_delete=models.CASCADE, related_name='import_jobs',
                                 null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                             null=True, blank=True, related_name='import_jobs')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    events = models.JSONField(default=list)
    result = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.aircraft:
            return f"ImportJob {self.id} ({self.status}) - {self.aircraft.tail_number}"
        return f"ImportJob {self.id} ({self.status})"


class ConsumableRecord(models.Model):
    RECORD_TYPE_OIL = 'oil'
    RECORD_TYPE_FUEL = 'fuel'
    RECORD_TYPE_CHOICES = [
        (RECORD_TYPE_OIL, 'Oil'),
        (RECORD_TYPE_FUEL, 'Fuel'),
    ]

    id = models.UUIDField(primary_key=True, blank=False, default=uuid.uuid4, editable=False)
    record_type = models.CharField(max_length=10, choices=RECORD_TYPE_CHOICES)
    aircraft = models.ForeignKey(core_models.Aircraft, related_name='consumable_records', on_delete=models.CASCADE)
    date = models.DateField()
    quantity_added = models.DecimalField(max_digits=6, decimal_places=2)
    level_after = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    consumable_type = models.CharField(max_length=100, blank=True, help_text="e.g. 'Aeroshell W100' for oil or '100LL' for fuel")
    flight_hours = models.DecimalField(max_digits=8, decimal_places=1, help_text="Aircraft hours at time of record")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        if self.record_type == self.RECORD_TYPE_OIL:
            return f"{self.aircraft.tail_number} - Oil {self.quantity_added}qt @ {self.flight_hours}hrs - {self.date}"
        return f"{self.aircraft.tail_number} - Fuel {self.quantity_added}gal @ {self.flight_hours}hrs - {self.date}"

