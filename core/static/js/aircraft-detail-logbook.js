function logbookMixin() {
    return {
        // Logbook state
        logbookEntries: [],
        logbookLoaded: false,
        logbookModalOpen: false,
        editingLogEntry: null,
        logbookSubmitting: false,
        logbookImageFiles: [],
        logbookForm: {
            date: '',
            entry_type: 'MAINTENANCE',
            log_type: 'AC',
            text: '',
            aircraft_hours_at_entry: '',
            signoff_person: '',
            signoff_location: '',
            link_ad_id: '',
            document_collection: '',
        },

        // Document collections (loaded on demand for modals)
        aircraftCollections: [],
        collectionsLoaded: false,

        async loadLogbookEntries() {
            try {
                const response = await fetch(`/api/logbook-entries/?aircraft=${this.aircraftId}`);
                const data = await response.json();
                this.logbookEntries = data.results || data;
                this.logbookLoaded = true;
            } catch (error) {
                console.error('Error loading logbook entries:', error);
                showNotification('Failed to load logbook entries', 'danger');
            }
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

        openLogbookModal(linkAdId) {
            this.editingLogEntry = null;
            this.logbookImageFiles = [];
            this.logbookForm = {
                date: new Date().toISOString().split('T')[0],
                entry_type: 'MAINTENANCE',
                log_type: 'AC',
                text: '',
                aircraft_hours_at_entry: this.aircraft ? parseFloat(this.aircraft.flight_time || 0).toFixed(1) : '',
                signoff_person: '',
                signoff_location: '',
                link_ad_id: linkAdId || '',
                document_collection: '',
            };
            this.loadCollectionsForModal();
            this.logbookModalOpen = true;
        },

        editLogEntry(entry) {
            this.editingLogEntry = entry;
            this.logbookImageFiles = [];
            this.logbookForm = {
                date: entry.date || '',
                entry_type: entry.entry_type || 'MAINTENANCE',
                log_type: entry.log_type || 'AC',
                text: entry.text || '',
                aircraft_hours_at_entry: entry.aircraft_hours_at_entry || '',
                signoff_person: entry.signoff_person || '',
                signoff_location: entry.signoff_location || '',
                link_ad_id: '',
                document_collection: '',
            };
            this.loadCollectionsForModal();
            this.logbookModalOpen = true;
        },

        closeLogbookModal() {
            this.logbookModalOpen = false;
            this.editingLogEntry = null;
            this.logbookImageFiles = [];
        },

        onLogbookFilesSelected(event) {
            this.logbookImageFiles = Array.from(event.target.files);
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
                if (logImageUrl) data.log_image = logImageUrl;

                let response;
                if (this.editingLogEntry) {
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

                    // Step 3: If an AD was selected, record compliance linked to this entry
                    if (!this.editingLogEntry && this.logbookForm.link_ad_id) {
                        const complianceData = {
                            ad: this.logbookForm.link_ad_id,
                            date_complied: this.logbookForm.date,
                            compliance_notes: this.logbookForm.text,
                            permanent: false,
                            next_due_at_time: 0,
                            logbook_entry: entryData.id,
                        };
                        await fetch(`/api/aircraft/${this.aircraftId}/compliance/`, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-CSRFToken': getCookie('csrftoken'),
                            },
                            body: JSON.stringify(complianceData),
                        });
                        this.adsLoaded = false;
                        await this.loadAds();
                    }

                    showNotification(
                        this.editingLogEntry ? 'Log entry updated' : 'Log entry created',
                        'success'
                    );
                    this.closeLogbookModal();
                    this.logbookLoaded = false;
                    await this.loadLogbookEntries();
                    await this.loadData();
                    if (this.documentsLoaded) {
                        this.documentsLoaded = false;
                        await this.loadDocuments();
                    }
                } else {
                    const errorData = await response.json();
                    const msg = typeof errorData === 'object'
                        ? Object.values(errorData).flat().join(', ')
                        : 'Failed to save log entry';
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

        async viewLogEntryDocument(log) {
            const docId = this.extractIdFromUrl(log.log_image);
            if (!docId) return;
            try {
                const resp = await fetch(`/api/documents/${docId}/`);
                if (resp.ok) {
                    const doc = await resp.json();
                    this.openDocumentViewer(doc, 'Logbook Document');
                }
            } catch (error) {
                console.error('Error loading logbook document:', error);
            }
        },
    };
}
