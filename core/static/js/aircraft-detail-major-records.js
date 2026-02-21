function majorRecordsMixin() {
    return {
        majorRecords: [],
        majorRecordsLoaded: false,
        majorRecordModalOpen: false,
        editingMajorRecord: null,
        majorRecordSubmitting: false,
        majorRecordFilter: 'all',
        openRelatedPopup: null,
        majorRecordForm: {
            record_type: 'repair',
            title: '',
            description: '',
            date_performed: '',
            performed_by: '',
            component: '',
            form_337_document: '',
            stc_number: '',
            stc_holder: '',
            stc_document: '',
            logbook_entry: '',
            aircraft_hours: '',
            notes: '',
        },

        get filteredMajorRecords() {
            if (this.majorRecordFilter === 'all') return this.majorRecords;
            return this.majorRecords.filter(r => r.record_type === this.majorRecordFilter);
        },

        get majorRepairs() {
            return this.majorRecords.filter(r => r.record_type === 'repair');
        },

        get majorAlterations() {
            return this.majorRecords.filter(r => r.record_type === 'alteration');
        },

        async loadMajorRecords() {
            try {
                const response = await fetch(`/api/aircraft/${this.aircraftId}/major_records/`);
                const data = await response.json();
                this.majorRecords = data || [];
                this.majorRecordsLoaded = true;
            } catch (error) {
                console.error('Error loading major records:', error);
                showNotification('Failed to load repairs & alterations', 'danger');
            }
        },

        openMajorRecordModal(type) {
            this.editingMajorRecord = null;
            this.majorRecordForm = {
                record_type: type || 'repair',
                title: '',
                description: '',
                date_performed: new Date().toISOString().split('T')[0],
                performed_by: '',
                component: '',
                form_337_document: '',
                stc_number: '',
                stc_holder: '',
                stc_document: '',
                logbook_entry: '',
                aircraft_hours: this.aircraft ? parseFloat(this.aircraft.flight_time || 0).toFixed(1) : '',
                notes: '',
            };
            this.pickerInit('majorRecordForm', 'logbook_entry', '');
            if (!this.documentsLoaded) this.loadDocuments();
            this.majorRecordModalOpen = true;
        },

        async editMajorRecord(record) {
            this.editingMajorRecord = record;
            const lbId = record.logbook_entry
                ? (this.extractIdFromUrl(record.logbook_entry) || record.logbook_entry)
                : '';
            this.majorRecordForm = {
                record_type: record.record_type,
                title: record.title,
                description: record.description || '',
                date_performed: record.date_performed,
                performed_by: record.performed_by || '',
                component: record.component || '',
                form_337_document: record.form_337_document || '',
                stc_number: record.stc_number || '',
                stc_holder: record.stc_holder || '',
                stc_document: record.stc_document || '',
                logbook_entry: lbId,
                aircraft_hours: record.aircraft_hours != null ? parseFloat(record.aircraft_hours).toFixed(1) : '',
                notes: record.notes || '',
            };
            await this.pickerInit('majorRecordForm', 'logbook_entry', lbId);
            if (!this.documentsLoaded) this.loadDocuments();
            this.majorRecordModalOpen = true;
        },

        closeMajorRecordModal() {
            this.majorRecordModalOpen = false;
            this.pickerBrowseOpen = false;
            this.editingMajorRecord = null;
        },

        async saveMajorRecord() {
            if (!this.majorRecordForm.title || !this.majorRecordForm.date_performed || this.majorRecordSubmitting) return;
            this.majorRecordSubmitting = true;
            try {
                const payload = {
                    record_type: this.majorRecordForm.record_type,
                    title: this.majorRecordForm.title,
                    description: this.majorRecordForm.description,
                    date_performed: this.majorRecordForm.date_performed,
                    performed_by: this.majorRecordForm.performed_by,
                    component: this.majorRecordForm.component || null,
                    form_337_document: this.majorRecordForm.form_337_document || null,
                    stc_number: this.majorRecordForm.stc_number,
                    stc_holder: this.majorRecordForm.stc_holder,
                    stc_document: this.majorRecordForm.stc_document || null,
                    logbook_entry: this.majorRecordForm.logbook_entry || null,
                    aircraft_hours: this.majorRecordForm.aircraft_hours ? parseFloat(this.majorRecordForm.aircraft_hours) : null,
                    notes: this.majorRecordForm.notes,
                };

                let response;
                if (this.editingMajorRecord) {
                    response = await apiRequest(`/api/major-records/${this.editingMajorRecord.id}/`, {
                        method: 'PATCH',
                        body: JSON.stringify(payload),
                    });
                } else {
                    response = await apiRequest(`/api/aircraft/${this.aircraftId}/major_records/`, {
                        method: 'POST',
                        body: JSON.stringify(payload),
                    });
                }

                if (response.ok) {
                    showNotification(
                        this.editingMajorRecord ? 'Record updated' : 'Record created',
                        'success'
                    );
                    this.closeMajorRecordModal();
                    await this.loadMajorRecords();
                    await this.loadData();
                } else {
                    showNotification(formatApiError(response.data, 'Failed to save record'), 'danger');
                }
            } catch (error) {
                console.error('Error saving major record:', error);
                showNotification('Error saving record', 'danger');
            } finally {
                this.majorRecordSubmitting = false;
            }
        },

        async deleteMajorRecord(record) {
            const label = record.record_type === 'repair' ? 'repair' : 'alteration';
            if (!confirm(`Delete this major ${label} "${record.title}"? This cannot be undone.`)) return;
            try {
                const response = await apiRequest(`/api/major-records/${record.id}/`, {
                    method: 'DELETE',
                });
                if (response.ok) {
                    showNotification('Record deleted', 'success');
                    await this.loadMajorRecords();
                    await this.loadData();
                } else {
                    showNotification('Failed to delete record', 'danger');
                }
            } catch (error) {
                console.error('Error deleting major record:', error);
                showNotification('Error deleting record', 'danger');
            }
        },

        // Returns true if a document should be shown as a clickable link.
        // In public view, only show links for documents that are in the pre-loaded visible set.
        canViewDocument(docId) {
            if (!docId) return false;
            if (!this.isPublicView) return true;
            const allDocs = (this.documentCollections || [])
                .flatMap(c => c.documents || [])
                .concat(this.uncollectedDocuments || []);
            return allDocs.some(d => d.id === docId);
        },

        // Quick-view helpers — reuse existing logbook entry detail modal and document viewer

        viewMajorRecordLogEntry(record) {
            if (record.logbook_entry) {
                this.viewLogEntryFromCompliance(record.logbook_entry);
            }
        },

        viewMajorRecordDocument(docId, docName) {
            if (!docId) return;
            // Look up the full document object from loaded documents
            const allDocs = (this.documentCollections || [])
                .flatMap(c => c.documents)
                .concat(this.uncollectedDocuments || []);
            const doc = allDocs.find(d => d.id === docId);
            if (doc) {
                this.openDocumentViewer(doc, docName || doc.name);
            } else {
                // Documents tab may not be loaded yet — load and retry
                this.loadDocuments().then(() => {
                    const allDocsRetry = (this.documentCollections || [])
                        .flatMap(c => c.documents)
                        .concat(this.uncollectedDocuments || []);
                    const found = allDocsRetry.find(d => d.id === docId);
                    if (found) {
                        this.openDocumentViewer(found, docName || found.name);
                    } else {
                        showNotification('Document not found', 'warning');
                    }
                });
            }
        },
    };
}
