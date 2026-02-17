# Major Repairs & Alterations — Implementation Plan

Replace the unused `STCApplication` model with a comprehensive system for tracking major repairs and major alterations per FAA regulations. One new tab ("Repairs & Alterations") on the aircraft detail page covers both, visually separated.

---

## 1. Data Model

### Remove `STCApplication`

- Delete the `STCApplication` class from `health/models.py`
- Remove `STCApplicationSerializer` from `health/serializers.py`
- Remove `STCApplicationViewSet` from `health/views.py`
- Remove the `stcs` router registration from `urls.py`
- Remove `'stcs'` from the `AircraftSerializer` and `ComponentSerializer` field lists
- Remove `STCApplication` from `admin.py`
- Remove all imports referencing `STCApplication`
- Generate a migration that deletes the `STCApplication` table

### New Model: `MajorRepairAlteration`

A single model covering both major repairs and major alterations (distinguished by a `record_type` field).

```python
RECORD_TYPES = (
    ('repair', 'Major Repair'),
    ('alteration', 'Major Alteration'),
)

class MajorRepairAlteration(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    aircraft = models.ForeignKey(Aircraft, related_name='major_records', on_delete=models.CASCADE)
    record_type = models.CharField(max_length=20, choices=RECORD_TYPES)

    # Description
    title = models.CharField(max_length=254, help_text="Brief title, e.g. 'Longeron repair' or 'STC SA00001SE installation'")
    description = models.TextField(blank=True, help_text="Detailed description of the work performed")
    date_performed = models.DateField(help_text="Date the repair or alteration was completed")
    performed_by = models.CharField(max_length=254, blank=True, help_text="Mechanic, shop, or IA who performed the work")

    # What was worked on
    component = models.ForeignKey(Component, related_name='major_records', blank=True, null=True, on_delete=models.SET_NULL,
                                  help_text="Component this applies to (engine, prop, etc.), if applicable")

    # FAA Form 337
    form_337_number = models.CharField(max_length=100, blank=True, help_text="FAA Form 337 number, if assigned")
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
```

**Design decisions:**
- Single model with `record_type` rather than two models — the fields are nearly identical, and this allows a unified API and tab.
- STC fields (`stc_number`, `stc_holder`, `stc_document`) are optional and only relevant for alterations. The form/UI will conditionally show these when `record_type == 'alteration'`.
- `form_337_document` and `stc_document` are FKs to `Document` (not M2M) since each record typically has one Form 337 and one STC data package. Users can add additional related documents to the `Document` collection.
- `component` uses `SET_NULL` (not `CASCADE`) — deleting a component shouldn't erase the repair/alteration record.
- `logbook_entry` uses `SET_NULL` for the same reason.

---

## 2. Migration

Generate with `python manage.py makemigrations health`. This will produce a single migration that:
1. Deletes the `STCApplication` table (and its M2M `stcapplication_documents` table)
2. Creates the `MajorRepairAlteration` table

If there is any data in `STCApplication` in production, we should note it can be migrated manually. Since the model has no UI and likely has no production data, a straight delete is fine.

---

## 3. Serializers (`health/serializers.py`)

### `MajorRepairAlterationNestedSerializer`

Used for reading records in the aircraft detail API response and also for create/update (with `read_only_fields`).

```python
class MajorRepairAlterationNestedSerializer(serializers.ModelSerializer):
    record_type_display = serializers.CharField(source='get_record_type_display', read_only=True)
    component_name = serializers.SerializerMethodField()
    form_337_document_name = serializers.CharField(source='form_337_document.name', read_only=True, default=None)
    stc_document_name = serializers.CharField(source='stc_document.name', read_only=True, default=None)
    logbook_entry_date = serializers.DateField(source='logbook_entry.date', read_only=True, default=None)

    class Meta:
        model = MajorRepairAlteration
        fields = [
            'id', 'aircraft', 'record_type', 'record_type_display',
            'title', 'description', 'date_performed', 'performed_by',
            'component', 'component_name',
            'form_337_number', 'form_337_document', 'form_337_document_name',
            'stc_number', 'stc_holder', 'stc_document', 'stc_document_name',
            'logbook_entry', 'logbook_entry_date',
            'aircraft_hours', 'notes', 'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'record_type_display', 'component_name',
                            'form_337_document_name', 'stc_document_name', 'logbook_entry_date']

    def get_component_name(self, obj):
        if obj.component:
            name = obj.component.component_type.name
            if obj.component.install_location:
                name += f" ({obj.component.install_location})"
            return name
        return None
```

Remove the old `STCApplicationSerializer`.

---

## 4. ViewSet and API Endpoints

### Custom Action on `AircraftViewSet` (`core/views.py`)

Add a `major_records` custom action following the same pattern as `ads`, `squawks`, etc:

```python
@action(detail=True, methods=['get', 'post'], url_path='major_records')
def major_records(self, request, pk=None):
    aircraft = self.get_object()
    if request.method == 'GET':
        records = MajorRepairAlteration.objects.filter(aircraft=aircraft)
        serializer = MajorRepairAlterationNestedSerializer(records, many=True)
        return Response(serializer.data)
    else:
        serializer = MajorRepairAlterationNestedSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        record = serializer.save(aircraft=aircraft)
        log_event(aircraft, 'major_record', f'{record.get_record_type_display()} created: {record.title}', user=request.user)
        return Response(MajorRepairAlterationNestedSerializer(record).data, status=status.HTTP_201_CREATED)
```

### Standalone ViewSet (`health/views.py`)

Add `MajorRepairAlterationViewSet` with `AircraftScopedMixin` and `EventLoggingMixin` for update/delete operations:

```python
class MajorRepairAlterationViewSet(AircraftScopedMixin, EventLoggingMixin, viewsets.ModelViewSet):
    queryset = MajorRepairAlteration.objects.all()
    serializer_class = MajorRepairAlterationNestedSerializer
    event_category = 'major_record'
    aircraft_fk_path = 'aircraft'
    event_name_created = 'Major record created'
    event_name_updated = 'Major record updated'
    event_name_deleted = 'Major record deleted'
```

Register in `urls.py`:
```python
router.register(r'major-records', health_views.MajorRepairAlterationViewSet)
```

### Permissions

- `major_records` on `AircraftViewSet`: owner-level (add to `IsAircraftOwnerOrAdmin` action list) — only owners/admins can create/edit/delete repairs and alterations.
- The standalone viewset inherits from `AircraftScopedMixin` which handles per-model permissions.

### Event Category

Add `'major_record'` to `EVENT_CATEGORIES` in `core/models.py`.

---

## 5. AircraftSerializer Updates

- Remove `'stcs'` from `AircraftSerializer.Meta.fields`
- No need to add `'major_records'` to the serializer's depth-1 fields — the data will be fetched by the frontend via the custom action endpoint, same as ADs and inspections.

---

## 6. Frontend: Alpine.js Mixin (`core/static/js/aircraft-detail-major-records.js`)

New mixin file: `majorRecordsMixin()`.

### State
```javascript
majorRecords: [],             // all records
majorRecordForm: { ... },     // create/edit form state
majorRecordModalOpen: false,
editingMajorRecord: null,     // null = creating, object = editing
majorRecordFilter: 'all',     // 'all', 'repair', 'alteration'
```

### Computed Properties
```javascript
get filteredMajorRecords()    // filter by record_type based on majorRecordFilter
get majorRepairs()            // records where record_type === 'repair'
get majorAlterations()        // records where record_type === 'alteration'
```

### Methods
```javascript
loadMajorRecords()            // GET /api/aircraft/{id}/major_records/
openMajorRecordModal(type)    // open modal pre-set to 'repair' or 'alteration'
editMajorRecord(record)       // populate form for editing
saveMajorRecord()             // POST or PATCH
deleteMajorRecord(record)     // DELETE with confirmation
resetMajorRecordForm()
```

### Data Loading
- Call `loadMajorRecords()` from the existing `loadData()` flow in the composer (same pattern as `loadAds()`, `loadInspections()`, etc.)
- For public views, include in `_loadPublicData()` if the summary endpoint returns this data; otherwise skip (repairs/alterations are owner-level, so public view may not need them — or we can include them read-only for transparency).

---

## 7. Frontend: Template Tab (`core/templates/aircraft_detail.html`)

### Tab Button
Add between the "Inspections" and "Oil" tabs:

```html
<li class="pf-v5-c-tabs__item" :class="{ 'pf-m-current': activeTab === 'major-records' }">
    <button class="pf-v5-c-tabs__link" @click="activeTab = 'major-records'">
        <span class="pf-v5-c-tabs__item-text">Repairs &amp; Alterations</span>
    </button>
</li>
```

### Tab Content

The tab content shows two visually separated sections on a single tab:

```
┌──────────────────────────────────────────────────────┐
│  Repairs & Alterations                    [+ Repair] [+ Alteration]  │
│                                                                       │
│  Filter: [All] [Repairs] [Alterations]                               │
│                                                                       │
│  ── Major Repairs ──────────────────────────────────────────          │
│  │ Title        │ Date       │ Component │ Form 337 │ Actions │      │
│  │ Longeron fix │ 2024-03-15 │ Airframe  │ 337-1234 │ ✏️ 🗑️    │      │
│  │ ...          │            │           │          │         │      │
│                                                                       │
│  ── Major Alterations ──────────────────────────────────────          │
│  │ Title        │ Date       │ Component │ STC #     │ Form 337 │ …  │
│  │ Tip tank STC │ 2023-06-01 │ Airframe  │ SA00123   │ 337-5678 │ …  │
│  │ ...          │            │           │           │          │    │
└──────────────────────────────────────────────────────┘
```

**Key layout decisions:**
- When filter is "All" (default), show both sections with headers. When "Repairs" or "Alterations", show only that section.
- Major Repairs table columns: Title, Date Performed, Component, Performed By, Form 337 #, Actions (edit/delete).
- Major Alterations table columns: Title, Date Performed, Component, STC Number, STC Holder, Form 337 #, Actions (edit/delete).
- Clicking a Form 337 # or STC document link opens the document viewer (same as existing document links).
- Clicking a logbook entry link scrolls/switches to the logbook tab filtered to that entry (or opens in a modal).
- Empty states: "No major repairs recorded" / "No major alterations recorded" with contextual add button.
- Action buttons hidden for non-owners (using `x-show="isOwner"`).

### Create/Edit Modal

A single modal for both types. The `record_type` is pre-selected based on which button was clicked and displayed as a read-only label (or selectable dropdown if editing).

**Form fields:**
- Record Type: radio/select (Major Repair / Major Alteration)
- Title: text input (required)
- Date Performed: date picker (required)
- Description: textarea
- Performed By: text input
- Component: dropdown (aircraft components) — optional
- Aircraft Hours: number input — optional, auto-populated with current aircraft hours
- Form 337 Number: text input
- Form 337 Document: dropdown (existing documents) — optional
- **STC fields (shown only when record_type is 'alteration'):**
  - STC Number: text input
  - STC Holder: text input
  - STC Document: dropdown (existing documents) — optional
- Logbook Entry: dropdown (existing logbook entries) — optional
- Notes: textarea

---

## 8. Composer Update (`core/static/js/aircraft-detail.js`)

- Import and merge `majorRecordsMixin()` into the `aircraftDetail()` function.
- Call `this.loadMajorRecords()` in `loadData()`.

---

## 9. Public Sharing

### Summary Endpoint

Add major records to the `/api/shared/<token>/` summary response — these are factual records about the aircraft and are reasonable to include in a public/shared view (read-only). Add a `major_records` key to the summary JSON, fetched via `MajorRepairAlterationNestedSerializer`.

### Public Template

The "Repairs & Alterations" tab should appear in the public view but with no add/edit/delete buttons (the `isPublicView` / `isOwner` guards handle this automatically).

---

## 10. Admin Registration

Register `MajorRepairAlteration` in `health/admin.py` with a basic `ModelAdmin`:

```python
@admin.register(MajorRepairAlteration)
class MajorRepairAlterationAdmin(admin.ModelAdmin):
    list_display = ('title', 'record_type', 'aircraft', 'date_performed', 'component')
    list_filter = ('record_type', 'aircraft')
    search_fields = ('title', 'description', 'stc_number', 'form_337_number')
```

---

## 11. CLAUDE.md Updates

After implementation:
- Add `MajorRepairAlteration` to the model/mixin documentation tables
- Add `aircraft-detail-major-records.js` / `majorRecordsMixin()` to the mixin table
- Add `major_records` to the custom actions table on `AircraftViewSet`
- Add `'major_record'` to the event categories list
- Update the API endpoint naming section with `/api/major-records/` and the custom action
- Remove all references to `STCApplication` and `stcs`

---

## Implementation Order

1. **Model changes** — Delete `STCApplication`, create `MajorRepairAlteration`, generate migration
2. **Serializers** — Delete `STCApplicationSerializer`, create `MajorRepairAlterationNestedSerializer`
3. **Views** — Delete `STCApplicationViewSet`, create `MajorRepairAlterationViewSet`, add `major_records` action to `AircraftViewSet`
4. **URL routing** — Swap `stcs` route for `major-records`
5. **Event category** — Add `'major_record'` to `EVENT_CATEGORIES`
6. **Admin** — Swap admin registration
7. **Run migration** — `makemigrations` + `migrate`
8. **Verify backend** — `python manage.py check`, test API endpoints manually
9. **Frontend mixin** — Create `aircraft-detail-major-records.js`
10. **Composer** — Add mixin to `aircraft-detail.js`
11. **Template** — Add tab button, tab content, and modal to `aircraft_detail.html`; add script tag
12. **Public sharing** — Add to summary endpoint and public template data loading
13. **CLAUDE.md** — Update documentation
