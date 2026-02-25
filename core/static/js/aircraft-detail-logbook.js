function logbookMixin() {
    return {
        // Logbook state
        logbookEntries: [],
        logbookLoaded: false,
        logbookLoading: false,
        logbookActiveTab: 'ALL',         // 'ALL' | 'AC' | 'ENG' | 'PROP' | 'OTHER'
        logbookSearch: '',               // text search input
        logbookEntryTypeFilter: '',      // '' = all entry types
        logbookTotal: 0,                 // total matching entries reported by API
        logbookSearchTimer: null,        // debounce handle
        logbookModalOpen: false,
        editingLogEntry: null,
        logbookSubmitting: false,
        logbookImageFiles: [],
        logbookExpandedEntries: {},      // { [id]: true } for expanded text
        logbookOpenOverflow: null,       // id of entry whose overflow menu is open
        logbookForm: {
            date: '',
            entry_type: 'MAINTENANCE',
            log_type: 'AC',
            text: '',
            aircraft_hours_at_entry: '',
            signoff_person: '',
            signoff_location: '',
            document_collection: '',
            page_number: '',
        },
        logbookAssociations: { ads: [], inspections: [], squawks: [] },

        // Related documents state
        logbookRelatedDocs: [],         // [{document_id: ''}] for linking existing docs
        logbookRelatedDocFiles: [],     // Files to upload as new related documents
        logbookRelatedDocType: 'OTHER', // doc_type for new uploaded related docs
        logbookExistingRelatedDocs: [], // populated in edit mode from related_documents_detail

        // Document collections (loaded on demand for modals)
        aircraftCollections: [],
        collectionsLoaded: false,

        // Aircraft documents (loaded on demand for related doc picker)
        aircraftDocuments: [],
        aircraftDocumentsLoaded: false,

        get logbookHasMore() {
            return this.logbookEntries.length < this.logbookTotal;
        },

        get availableAdsForLogbook() {
            const selectedIds = this.logbookAssociations.ads.map(a => a.ad_id);
            return (this.applicableAds || []).filter(ad => !selectedIds.includes(ad.id));
        },

        get availableInspectionsForLogbook() {
            const selectedIds = this.logbookAssociations.inspections.map(i => i.inspection_type_id);
            return (this.inspectionTypes || []).filter(it => !selectedIds.includes(it.id));
        },

        get availableSquawksForLogbook() {
            const selectedIds = this.logbookAssociations.squawks.map(s => s.squawk_id);
            return (this.activeSquawks || []).filter(sq => !selectedIds.includes(sq.id));
        },

        get availableDocsForLogbook() {
            const linkedIds = [
                ...this.logbookExistingRelatedDocs.map(d => d.id),
                ...this.logbookRelatedDocs.map(d => d.document_id),
            ];
            return this.aircraftDocuments.filter(d => !linkedIds.includes(d.id));
        },

        addAdAssociation() {
            this.logbookAssociations.ads.push({ ad_id: '', permanent: false, next_due_at_time: '' });
        },

        removeAdAssociation(idx) {
            this.logbookAssociations.ads.splice(idx, 1);
        },

        addInspectionAssociation() {
            this.logbookAssociations.inspections.push({ inspection_type_id: '' });
        },

        removeInspectionAssociation(idx) {
            this.logbookAssociations.inspections.splice(idx, 1);
        },

        addSquawkAssociation() {
            this.logbookAssociations.squawks.push({ squawk_id: '', resolve: true });
        },

        removeSquawkAssociation(idx) {
            this.logbookAssociations.squawks.splice(idx, 1);
        },

        addRelatedDoc() {
            this.logbookRelatedDocs.push({ document_id: '' });
        },

        removeRelatedDoc(idx) {
            this.logbookRelatedDocs.splice(idx, 1);
        },

        onRelatedDocFilesSelected(event) {
            this.logbookRelatedDocFiles = Array.from(event.target.files);
        },

        removeRelatedDocFile(idx) {
            this.logbookRelatedDocFiles.splice(idx, 1);
        },

        async loadAircraftDocuments() {
            if (this.aircraftDocumentsLoaded) return;
            try {
                const resp = await fetch(`/api/documents/?aircraft=${this.aircraftId}`);
                const data = await resp.json();
                this.aircraftDocuments = (data.results || data).map(d => ({
                    id: d.id,
                    name: d.name,
                    doc_type: d.doc_type,
                    doc_type_display: d.doc_type_display,
                }));
                this.aircraftDocumentsLoaded = true;
            } catch (error) {
                console.error('Error loading aircraft documents:', error);
            }
        },

        logAttachmentCount(log) {
            const mainDoc = (log.log_image && (!this.isPublicView || log.log_image_shared)) ? 1 : 0;
            const relatedDocs = (log.related_documents_detail || []).length;
            return mainDoc + relatedDocs;
        },

        toggleLogExpand(logId) {
            this.logbookExpandedEntries = { ...this.logbookExpandedEntries, [logId]: true };
        },

        async loadLogbookEntries(append = false) {
            if (this.logbookLoading) return;
            this.logbookLoading = true;
            const offset = append ? this.logbookEntries.length : 0;
            if (!append) {
                this.logbookEntries = [];
                this.logbookTotal = 0;
            }

            try {
                let url;
                if (this.isPublicView) {
                    const params = new URLSearchParams({ offset, limit: 25 });
                    if (this.logbookActiveTab !== 'ALL') params.set('log_type', this.logbookActiveTab);
                    if (this.logbookEntryTypeFilter) params.set('entry_type', this.logbookEntryTypeFilter);
                    if (this.logbookSearch.trim()) params.set('search', this.logbookSearch.trim());
                    url = `/api/shared/${this._publicShareToken}/logbook-entries/?${params}`;
                } else {
                    const params = new URLSearchParams({ aircraft: this.aircraftId, offset, limit: 25 });
                    if (this.logbookActiveTab !== 'ALL') params.set('log_type', this.logbookActiveTab);
                    if (this.logbookEntryTypeFilter) params.set('entry_type', this.logbookEntryTypeFilter);
                    if (this.logbookSearch.trim()) params.set('search', this.logbookSearch.trim());
                    url = `/api/logbook-entries/?${params}`;
                }

                const response = await fetch(url);
                const data = await response.json();
                const newEntries = data.results || [];
                if (append) {
                    this.logbookEntries.push(...newEntries);
                } else {
                    this.logbookEntries = newEntries;
                }
                this.logbookTotal = data.count ?? 0;
                this.logbookLoaded = true;
            } catch (error) {
                console.error('Error loading logbook entries:', error);
                showNotification('Failed to load logbook entries', 'danger');
            } finally {
                this.logbookLoading = false;
            }
        },

        loadMoreLogbook() {
            this.loadLogbookEntries(true);
        },

        switchLogbookTab(tab) {
            this.logbookActiveTab = tab;
            this.logbookSearch = '';
            this.logbookEntryTypeFilter = '';
            this.loadLogbookEntries(false);
        },

        onLogbookSearchInput() {
            clearTimeout(this.logbookSearchTimer);
            this.logbookSearchTimer = setTimeout(() => this.loadLogbookEntries(false), 300);
        },

        logbookTabLabel(tab) {
            return { ALL: 'All', AC: 'Airframe', ENG: 'Engine', PROP: 'Propeller', OTHER: 'Other' }[tab] ?? tab;
        },

        async loadCollectionsForModal() {
            if (this.collectionsLoaded) return;
            try {
                const response = await fetch(`/api/document-collections/?aircraft=${this.aircraftId}`);
                const data = await response.json();
                this.aircraftCollections = data.results || data;
                this.collectionsLoaded = true;
            } catch (error) {
                console.error('Error loading collections:', error);
            }
        },

        openLogbookModal() {
            this.editingLogEntry = null;
            this.logbookImageFiles = [];
            this.logbookRelatedDocs = [];
            this.logbookRelatedDocFiles = [];
            this.logbookRelatedDocType = 'OTHER';
            this.logbookExistingRelatedDocs = [];
            this.logbookForm = {
                date: new Date().toISOString().split('T')[0],
                entry_type: 'MAINTENANCE',
                log_type: 'AC',
                text: '',
                aircraft_hours_at_entry: this.aircraft ? parseFloat(this.aircraft.flight_time || 0).toFixed(1) : '',
                signoff_person: '',
                signoff_location: '',
                document_collection: '',
                page_number: '',
            };
            this.logbookAssociations = { ads: [], inspections: [], squawks: [] };
            this.loadCollectionsForModal();
            this.loadAircraftDocuments();
            // Ensure inspection types are loaded for the associations section
            if (!this.inspectionsLoaded) {
                this.loadInspections();
            }
            this.logbookModalOpen = true;
        },

        editLogEntry(entry) {
            this.editingLogEntry = entry;
            this.logbookImageFiles = [];
            this.logbookRelatedDocs = [];
            this.logbookRelatedDocFiles = [];
            this.logbookRelatedDocType = 'OTHER';
            this.logbookExistingRelatedDocs = entry.related_documents_detail || [];
            this.logbookForm = {
                date: entry.date || '',
                entry_type: entry.entry_type || 'MAINTENANCE',
                log_type: entry.log_type || 'AC',
                text: entry.text || '',
                aircraft_hours_at_entry: entry.aircraft_hours_at_entry || '',
                signoff_person: entry.signoff_person || '',
                signoff_location: entry.signoff_location || '',
                document_collection: '',
                page_number: entry.page_number || '',
            };
            this.logbookAssociations = { ads: [], inspections: [], squawks: [] };
            this.loadCollectionsForModal();
            this.loadAircraftDocuments();
            this.logbookModalOpen = true;
        },

        closeLogbookModal() {
            this.logbookModalOpen = false;
            this.editingLogEntry = null;
            this.logbookImageFiles = [];
            this.logbookRelatedDocs = [];
            this.logbookRelatedDocFiles = [];
            this.logbookExistingRelatedDocs = [];
            this.logbookAssociations = { ads: [], inspections: [], squawks: [] };
        },

        onLogbookFilesSelected(event) {
            this.logbookImageFiles = Array.from(event.target.files);
        },

        async _uploadRelatedDocFiles() {
            // Upload files as new Document records and return their IDs
            const newDocIds = [];
            for (const file of this.logbookRelatedDocFiles) {
                const docPayload = {
                    aircraft: `/api/aircraft/${this.aircraftId}/`,
                    name: file.name,
                    doc_type: this.logbookRelatedDocType,
                    components: [],
                };
                const docResp = await apiRequest('/api/documents/', {
                    method: 'POST',
                    body: JSON.stringify(docPayload),
                });
                if (docResp.ok) {
                    const formData = new FormData();
                    formData.append('document', `/api/documents/${docResp.data.id}/`);
                    formData.append('image', file);
                    formData.append('notes', '');
                    await fetch('/api/document-images/', {
                        method: 'POST',
                        headers: { 'X-CSRFToken': getCookie('csrftoken') },
                        body: formData,
                    });
                    newDocIds.push(docResp.data.id);
                } else {
                    showNotification(`Failed to upload ${file.name}`, 'warning');
                }
            }
            return newDocIds;
        },

        _buildRelatedDocumentUrls(uploadedDocIds) {
            // Combine existing linked docs + newly selected docs + newly uploaded docs
            const allIds = [
                ...this.logbookExistingRelatedDocs.map(d => d.id),
                ...this.logbookRelatedDocs.filter(d => d.document_id).map(d => d.document_id),
                ...uploadedDocIds,
            ];
            // Deduplicate
            const unique = [...new Set(allIds)];
            return unique.map(id => `/api/documents/${id}/`);
        },

        async submitLogEntry() {
            if (this.logbookSubmitting) return;
            if (!this.logbookForm.text.trim()) {
                showNotification('Entry text is required', 'warning');
                return;
            }

            this.logbookSubmitting = true;
            try {
                // Step 1: If new files selected, create a document and upload images first
                let logImageUrl = null;
                if (this.logbookImageFiles.length > 0) {
                    const docPayload = {
                        aircraft: `/api/aircraft/${this.aircraftId}/`,
                        name: `Logbook - ${this.logbookForm.date}`,
                        doc_type: 'LOG',
                        components: [],
                    };
                    if (this.logbookForm.document_collection) {
                        docPayload.collection = `/api/document-collections/${this.logbookForm.document_collection}/`;
                    }
                    const docResp = await fetch('/api/documents/', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': getCookie('csrftoken'),
                        },
                        body: JSON.stringify(docPayload),
                    });
                    if (docResp.ok) {
                        const docData = await docResp.json();
                        logImageUrl = `/api/documents/${docData.id}/`;
                        for (const file of this.logbookImageFiles) {
                            const formData = new FormData();
                            formData.append('document', logImageUrl);
                            formData.append('image', file);
                            formData.append('notes', '');
                            await fetch('/api/document-images/', {
                                method: 'POST',
                                headers: { 'X-CSRFToken': getCookie('csrftoken') },
                                body: formData,
                            });
                        }
                    } else {
                        showNotification('Failed to create document for images', 'warning');
                    }
                }

                // Step 1b: Upload related document files
                const uploadedRelatedDocIds = await this._uploadRelatedDocFiles();

                // Step 2: Save the logbook entry
                const data = {
                    date: this.logbookForm.date,
                    entry_type: this.logbookForm.entry_type,
                    log_type: this.logbookForm.log_type,
                    text: this.logbookForm.text,
                };
                if (this.logbookForm.aircraft_hours_at_entry) {
                    data.aircraft_hours_at_entry = parseFloat(this.logbookForm.aircraft_hours_at_entry);
                }
                if (this.logbookForm.signoff_person) data.signoff_person = this.logbookForm.signoff_person;
                if (this.logbookForm.signoff_location) data.signoff_location = this.logbookForm.signoff_location;
                data.page_number = this.logbookForm.page_number ? parseInt(this.logbookForm.page_number) : null;
                if (logImageUrl) data.log_image = logImageUrl;

                // Include related documents (for both new and edit)
                const hasRelatedDocs = this.logbookExistingRelatedDocs.length > 0 ||
                    this.logbookRelatedDocs.some(d => d.document_id) ||
                    uploadedRelatedDocIds.length > 0;
                if (hasRelatedDocs) {
                    data.related_documents = this._buildRelatedDocumentUrls(uploadedRelatedDocIds);
                }

                let response;
                if (this.editingLogEntry) {
                    // Always send related_documents on edit to handle unlinking
                    data.related_documents = this._buildRelatedDocumentUrls(uploadedRelatedDocIds);
                    response = await fetch(`/api/logbook-entries/${this.editingLogEntry.id}/`, {
                        method: 'PATCH',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': getCookie('csrftoken'),
                        },
                        body: JSON.stringify(data),
                    });
                } else {
                    data.aircraft = `/api/aircraft/${this.aircraftId}/`;
                    response = await fetch('/api/logbook-entries/', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': getCookie('csrftoken'),
                        },
                        body: JSON.stringify(data),
                    });
                }

                if (response.ok) {
                    const entryData = await response.json();

                    // Step 3: Create associations in parallel (new entries only)
                    if (!this.editingLogEntry) {
                        const associationPromises = [];
                        let hasInspections = false;

                        for (const assoc of this.logbookAssociations.ads) {
                            if (!assoc.ad_id) continue;
                            const complianceData = {
                                ad: assoc.ad_id,
                                date_complied: this.logbookForm.date,
                                compliance_notes: this.logbookForm.text,
                                permanent: assoc.permanent || false,
                                next_due_at_time: assoc.next_due_at_time ? parseFloat(assoc.next_due_at_time) : 0,
                                logbook_entry: entryData.id,
                            };
                            associationPromises.push(
                                apiRequest(`/api/aircraft/${this.aircraftId}/compliance/`, {
                                    method: 'POST',
                                    body: JSON.stringify(complianceData),
                                })
                            );
                        }

                        for (const assoc of this.logbookAssociations.inspections) {
                            if (!assoc.inspection_type_id) continue;
                            hasInspections = true;
                            const inspData = {
                                inspection_type: assoc.inspection_type_id,
                                date: this.logbookForm.date,
                                notes: this.logbookForm.text,
                                logbook_entry: entryData.id,
                            };
                            if (this.logbookForm.aircraft_hours_at_entry) {
                                inspData.aircraft_hours = parseFloat(this.logbookForm.aircraft_hours_at_entry);
                            }
                            associationPromises.push(
                                apiRequest(`/api/aircraft/${this.aircraftId}/inspections/`, {
                                    method: 'POST',
                                    body: JSON.stringify(inspData),
                                })
                            );
                        }

                        for (const assoc of this.logbookAssociations.squawks) {
                            if (!assoc.squawk_id) continue;
                            associationPromises.push(
                                apiRequest(`/api/squawks/${assoc.squawk_id}/link_logbook/`, {
                                    method: 'POST',
                                    body: JSON.stringify({
                                        logbook_entry_id: entryData.id,
                                        resolve: assoc.resolve,
                                    }),
                                })
                            );
                        }

                        if (associationPromises.length > 0) {
                            const results = await Promise.allSettled(associationPromises);
                            const failed = results.filter(r => r.status === 'rejected' || (r.value && !r.value.ok));
                            if (failed.length > 0) {
                                showNotification(`${failed.length} association(s) failed to save`, 'warning');
                            }
                        }

                        // Refresh affected tabs
                        if (this.logbookAssociations.ads.some(a => a.ad_id)) {
                            this.adsLoaded = false;
                            await this.loadAds();
                        }
                        if (hasInspections) {
                            this.inspectionsLoaded = false;
                            await this.loadInspections();
                        }
                    }

                    showNotification(
                        this.editingLogEntry ? 'Log entry updated' : 'Log entry created',
                        'success'
                    );
                    this.closeLogbookModal();
                    this.logbookLoaded = false;
                    this.aircraftDocumentsLoaded = false;
                    await this.loadLogbookEntries();
                    await this.loadData();
                    if (this.documentsLoaded) {
                        this.documentsLoaded = false;
                        await this.loadDocuments();
                    }
                } else {
                    const errorData = await response.json();
                    const msg = formatApiError(errorData, 'Failed to save log entry');
                    showNotification(msg, 'danger');
                }
            } catch (error) {
                console.error('Error saving log entry:', error);
                showNotification('Error saving log entry', 'danger');
            } finally {
                this.logbookSubmitting = false;
            }
        },

        async deleteLogEntry(entry) {
            if (!confirm('Delete this logbook entry? This cannot be undone.')) return;

            try {
                const response = await fetch(`/api/logbook-entries/${entry.id}/`, {
                    method: 'DELETE',
                    headers: {
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                });

                if (response.ok || response.status === 204) {
                    showNotification('Log entry deleted', 'success');
                    this.logbookLoaded = false;
                    await this.loadLogbookEntries();
                    await this.loadData();
                } else {
                    showNotification('Failed to delete log entry', 'danger');
                }
            } catch (error) {
                console.error('Error deleting log entry:', error);
                showNotification('Error deleting log entry', 'danger');
            }
        },

        logbookEntryLabel(entry) {
            const date = this.formatDate(entry.date);
            const type = entry.entry_type || entry.log_type || '';
            const text = entry.text ? (entry.text.length > 60 ? entry.text.slice(0, 60) + '…' : entry.text) : '';
            const hrs = entry.aircraft_hours_at_entry ? ` · ${parseFloat(entry.aircraft_hours_at_entry).toFixed(1)} hrs` : '';
            return `${date}${hrs} — ${type}: ${text}`;
        },

        _findLoadedDocument(docId) {
            // Search already-loaded document data (used in public mode)
            for (const col of (this.documentCollections || [])) {
                for (const d of (col.documents || [])) {
                    if (d.id === docId) return d;
                }
            }
            for (const d of (this.uncollectedDocuments || [])) {
                if (d.id === docId) return d;
            }
            return null;
        },

        async viewLogEntryDocument(log) {
            const docId = this.extractIdFromUrl(log.log_image);
            if (!docId) return;
            try {
                if (this.isPublicView) {
                    const doc = this._findLoadedDocument(docId);
                    if (doc) {
                        const startPage = log.page_number ? log.page_number - 1 : 0;
                        this.openDocumentViewer(doc, 'Logbook Document', startPage);
                    }
                    return;
                }
                const resp = await fetch(`/api/documents/${docId}/`);
                if (resp.ok) {
                    const doc = await resp.json();
                    const startPage = log.page_number ? log.page_number - 1 : 0;
                    this.openDocumentViewer(doc, 'Logbook Document', startPage);
                }
            } catch (error) {
                console.error('Error loading logbook document:', error);
            }
        },

        async viewRelatedDocument(doc) {
            try {
                if (this.isPublicView) {
                    // In public mode, related_documents_detail already has images
                    this.openDocumentViewer(doc, doc.name || 'Related Document');
                    return;
                }
                const resp = await fetch(`/api/documents/${doc.id}/`);
                if (resp.ok) {
                    const fullDoc = await resp.json();
                    this.openDocumentViewer(fullDoc, doc.name || 'Related Document');
                }
            } catch (error) {
                console.error('Error loading related document:', error);
            }
        },

        removeExistingRelatedDoc(idx) {
            this.logbookExistingRelatedDocs.splice(idx, 1);
        },

        // ── Create Compliance Records from Logbook Entry (Flow A) ──────────────

        createRecordsModalOpen: false,
        createRecordsLoading: false,
        createRecordsSubmitting: false,
        createRecordsEntry: null,
        createRecordsDate: '',
        createRecordsHours: '',
        createRecordsAdSearch: '',
        createRecordsSelections: { inspections: [], ads: [] },

        get createRecordsFilteredAds() {
            const q = this.createRecordsAdSearch.trim().toLowerCase();
            if (!q) return this.createRecordsSelections.ads;
            return this.createRecordsSelections.ads.filter(ad =>
                ad.name.toLowerCase().includes(q) ||
                ad.short_description.toLowerCase().includes(q)
            );
        },

        get createRecordsTotalChecked() {
            return this.createRecordsSelections.inspections.filter(i => i.checked).length +
                   this.createRecordsSelections.ads.filter(a => a.checked).length;
        },

        async openCreateRecordsModal(entry) {
            this.createRecordsEntry = entry;
            this.createRecordsDate = entry.date || '';
            this.createRecordsHours = entry.aircraft_hours_at_entry
                ? parseFloat(entry.aircraft_hours_at_entry).toFixed(1)
                : '';
            this.createRecordsAdSearch = '';
            this.createRecordsSelections = { inspections: [], ads: [] };
            this.createRecordsLoading = true;
            this.createRecordsModalOpen = true;

            // Load inspections and ADs in parallel if not already loaded
            const loadPromises = [];
            if (!this.inspectionsLoaded) loadPromises.push(this.loadInspections());
            if (!this.adsLoaded) loadPromises.push(this.loadAds());
            if (loadPromises.length > 0) await Promise.all(loadPromises);

            this.createRecordsSelections = {
                inspections: this.inspectionTypes.map(it => ({
                    id: it.id,
                    name: it.name,
                    checked: false,
                })),
                ads: this.applicableAds.map(ad => ({
                    id: ad.id,
                    name: ad.name,
                    short_description: ad.short_description,
                    recurring: ad.recurring,
                    recurring_hours: parseFloat(ad.recurring_hours) || 0,
                    checked: false,
                    permanent: false,
                    next_due_at_time: '',
                    compliance_notes: '',
                })),
            };
            this.createRecordsLoading = false;
        },

        closeCreateRecordsModal() {
            this.createRecordsModalOpen = false;
            this.createRecordsEntry = null;
            this.createRecordsSelections = { inspections: [], ads: [] };
            this.createRecordsDate = '';
            this.createRecordsHours = '';
            this.createRecordsAdSearch = '';
            this.createRecordsLoading = false;
        },

        onCreateRecordsAdChecked(adItem) {
            // Auto-fill next_due_at_time when first checking a recurring AD
            if (adItem.checked && adItem.recurring && adItem.recurring_hours > 0 &&
                    this.createRecordsHours && !adItem.next_due_at_time) {
                adItem.next_due_at_time = (
                    parseFloat(this.createRecordsHours) + adItem.recurring_hours
                ).toFixed(1);
            }
        },

        async submitCreateRecords() {
            if (this.createRecordsSubmitting) return;
            const checkedInspections = this.createRecordsSelections.inspections.filter(i => i.checked);
            const checkedAds = this.createRecordsSelections.ads.filter(a => a.checked);
            if (checkedInspections.length === 0 && checkedAds.length === 0) {
                showNotification('Select at least one inspection or AD to record', 'warning');
                return;
            }
            if (!this.createRecordsDate) {
                showNotification('Date is required', 'warning');
                return;
            }

            this.createRecordsSubmitting = true;
            try {
                const promises = [];

                for (const insp of checkedInspections) {
                    const data = {
                        inspection_type: insp.id,
                        date: this.createRecordsDate,
                        logbook_entry: this.createRecordsEntry.id,
                    };
                    if (this.createRecordsHours) {
                        data.aircraft_hours = parseFloat(this.createRecordsHours);
                    }
                    promises.push(apiRequest(`/api/aircraft/${this.aircraftId}/inspections/`, {
                        method: 'POST',
                        body: JSON.stringify(data),
                    }));
                }

                for (const ad of checkedAds) {
                    const data = {
                        ad: ad.id,
                        date_complied: this.createRecordsDate,
                        compliance_notes: ad.compliance_notes || this.createRecordsEntry.text || '',
                        permanent: ad.permanent || false,
                        next_due_at_time: ad.permanent ? 0 : (parseFloat(ad.next_due_at_time) || 0),
                        logbook_entry: this.createRecordsEntry.id,
                    };
                    if (this.createRecordsHours) {
                        data.aircraft_hours_at_compliance = parseFloat(this.createRecordsHours);
                    }
                    promises.push(apiRequest(`/api/aircraft/${this.aircraftId}/compliance/`, {
                        method: 'POST',
                        body: JSON.stringify(data),
                    }));
                }

                const results = await Promise.allSettled(promises);
                const failures = results.filter(r => r.status === 'rejected' || (r.value && !r.value.ok));
                const successes = results.length - failures.length;

                if (failures.length > 0) {
                    showNotification(
                        `${successes} record(s) created, ${failures.length} failed — check the inspections and ADs tabs`,
                        'warning'
                    );
                } else {
                    const total = results.length;
                    showNotification(
                        `${total} compliance record${total !== 1 ? 's' : ''} created`,
                        'success'
                    );
                }

                // Refresh affected tabs
                if (checkedInspections.length > 0) {
                    this.inspectionsLoaded = false;
                    await this.loadInspections();
                }
                if (checkedAds.length > 0) {
                    this.adsLoaded = false;
                    await this.loadAds();
                }
                await this.loadData();

                this.closeCreateRecordsModal();
            } catch (error) {
                console.error('Error creating compliance records:', error);
                showNotification('Error creating records', 'danger');
            } finally {
                this.createRecordsSubmitting = false;
            }
        },
    };
}
