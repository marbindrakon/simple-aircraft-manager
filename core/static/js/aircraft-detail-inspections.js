function inspectionsMixin() {
    return {
        // Inspection tracking state
        inspectionTypes: [],
        allInspectionTypes: [],
        inspectionsLoaded: false,
        inspectionModalOpen: false,
        editingInspectionRecord: null,
        inspectionSubmitting: false,
        selectedInspectionType: null,
        inspectionForm: {
            date: '',
            aircraft_hours: '',
            logbook_entry_id: '',
        },
        inspectionTypeModalOpen: false,
        editingInspectionType: null,
        inspectionTypeSubmitting: false,
        selectedExistingInspectionTypeId: '',
        inspectionTypeForm: {
            name: '',
            required: true,
            recurring: false,
            recurring_hours: 0,
            recurring_months: 0,
            recurring_days: 0,
        },
        inspectionHistoryOpen: false,
        inspectionHistory: [],
        inspectionHistoryLoading: false,

        get inspectionIssueCount() {
            return this.inspectionTypes.filter(
                t => t.compliance_status === 'overdue' || t.compliance_status === 'never_completed'
            ).length;
        },

        async loadInspections() {
            try {
                const response = await fetch(`/api/aircraft/${this.aircraftId}/inspections/`);
                const data = await response.json();
                this.inspectionTypes = data.inspection_types || [];
                this.inspectionsLoaded = true;
            } catch (error) {
                console.error('Error loading inspections:', error);
                showNotification('Failed to load inspections', 'danger');
            }
        },

        async loadAllInspectionTypes() {
            try {
                const response = await fetch('/api/inspection-types/');
                const data = await response.json();
                this.allInspectionTypes = data.results || data;
            } catch (error) {
                console.error('Error loading inspection types:', error);
            }
        },

        get availableInspectionTypes() {
            const applicableIds = new Set(this.inspectionTypes.map(t => t.id));
            return this.allInspectionTypes.filter(t => !applicableIds.has(t.id));
        },

        openInspectionTypeModal() {
            this.editingInspectionType = null;
            this.selectedExistingInspectionTypeId = '';
            this.inspectionTypeForm = {
                name: '',
                required: true,
                recurring: false,
                recurring_hours: 0,
                recurring_months: 0,
                recurring_days: 0,
            };
            this.loadAllInspectionTypes();
            this.inspectionTypeModalOpen = true;
        },

        editInspectionType(insp) {
            this.editingInspectionType = insp;
            this.selectedExistingInspectionTypeId = '';
            this.inspectionTypeForm = {
                name: insp.name,
                required: insp.required,
                recurring: insp.recurring,
                recurring_hours: insp.recurring_hours || 0,
                recurring_months: insp.recurring_months || 0,
                recurring_days: insp.recurring_days || 0,
            };
            this.inspectionTypeModalOpen = true;
        },

        closeInspectionTypeModal() {
            this.inspectionTypeModalOpen = false;
            this.editingInspectionType = null;
        },

        async addExistingInspectionType() {
            if (!this.selectedExistingInspectionTypeId || this.inspectionTypeSubmitting) return;
            this.inspectionTypeSubmitting = true;
            try {
                const response = await fetch(`/api/aircraft/${this.aircraftId}/inspections/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                    body: JSON.stringify({ inspection_type_id: this.selectedExistingInspectionTypeId }),
                });

                if (response.ok) {
                    showNotification('Inspection type added', 'success');
                    this.closeInspectionTypeModal();
                    this.inspectionsLoaded = false;
                    await this.loadInspections();
                    await this.loadData();
                } else {
                    const errorData = await response.json();
                    showNotification(errorData.error || 'Failed to add inspection type', 'danger');
                }
            } catch (error) {
                console.error('Error adding inspection type:', error);
                showNotification('Error adding inspection type', 'danger');
            } finally {
                this.inspectionTypeSubmitting = false;
            }
        },

        async submitInspectionType() {
            if (!this.inspectionTypeForm.name || this.inspectionTypeSubmitting) return;
            this.inspectionTypeSubmitting = true;
            try {
                const payload = {
                    name: this.inspectionTypeForm.name,
                    required: this.inspectionTypeForm.required,
                    recurring: this.inspectionTypeForm.recurring,
                    recurring_hours: this.inspectionTypeForm.recurring ? parseFloat(this.inspectionTypeForm.recurring_hours) || 0 : 0,
                    recurring_months: this.inspectionTypeForm.recurring ? parseInt(this.inspectionTypeForm.recurring_months) || 0 : 0,
                    recurring_days: this.inspectionTypeForm.recurring ? parseInt(this.inspectionTypeForm.recurring_days) || 0 : 0,
                };

                let response;
                if (this.editingInspectionType) {
                    response = await fetch(`/api/inspection-types/${this.editingInspectionType.id}/`, {
                        method: 'PATCH',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': getCookie('csrftoken'),
                        },
                        body: JSON.stringify(payload),
                    });
                } else {
                    response = await fetch(`/api/aircraft/${this.aircraftId}/inspections/`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': getCookie('csrftoken'),
                        },
                        body: JSON.stringify({ create_type: true, ...payload }),
                    });
                }

                if (response.ok) {
                    showNotification(this.editingInspectionType ? 'Inspection type updated' : 'Inspection type created', 'success');
                    this.closeInspectionTypeModal();
                    this.inspectionsLoaded = false;
                    await this.loadInspections();
                    await this.loadData();
                } else {
                    const errorData = await response.json();
                    const msg = typeof errorData === 'object'
                        ? Object.values(errorData).flat().join(', ')
                        : 'Failed to save inspection type';
                    showNotification(msg, 'danger');
                }
            } catch (error) {
                console.error('Error saving inspection type:', error);
                showNotification('Error saving inspection type', 'danger');
            } finally {
                this.inspectionTypeSubmitting = false;
            }
        },

        async removeInspectionType(insp) {
            if (!confirm(`Remove "${insp.name}" from this aircraft?`)) return;
            try {
                const response = await fetch(`/api/aircraft/${this.aircraftId}/remove_inspection_type/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                    body: JSON.stringify({ inspection_type_id: insp.id }),
                });

                if (response.ok) {
                    showNotification('Inspection type removed', 'success');
                    this.inspectionsLoaded = false;
                    await this.loadInspections();
                    await this.loadData();
                } else {
                    showNotification('Failed to remove inspection type', 'danger');
                }
            } catch (error) {
                console.error('Error removing inspection type:', error);
                showNotification('Error removing inspection type', 'danger');
            }
        },

        openInspectionModal(insp) {
            this.editingInspectionRecord = null;
            this.selectedInspectionType = insp;
            this.inspectionForm = {
                date: new Date().toISOString().split('T')[0],
                aircraft_hours: this.aircraft ? parseFloat(this.aircraft.flight_time || 0).toFixed(1) : '',
                logbook_entry_id: '',
            };
            if (!this.logbookLoaded) this.loadLogbookEntries();
            this.inspectionModalOpen = true;
        },

        async editInspectionRecord(record) {
            this.editingInspectionRecord = record;
            const lbId = record.logbook_entry
                ? (this.extractIdFromUrl(record.logbook_entry) || record.logbook_entry)
                : '';
            this.inspectionForm = {
                date: record.date,
                aircraft_hours: record.aircraft_hours != null ? parseFloat(record.aircraft_hours).toFixed(1) : '',
                logbook_entry_id: lbId,
            };
            if (!this.logbookLoaded) await this.loadLogbookEntries();
            this.inspectionModalOpen = true;
        },

        closeInspectionModal() {
            this.inspectionModalOpen = false;
            this.editingInspectionRecord = null;
            this.selectedInspectionType = null;
        },

        async submitInspection() {
            if (this.inspectionSubmitting) return;
            this.inspectionSubmitting = true;
            try {
                const data = {
                    date: this.inspectionForm.date,
                    aircraft_hours: this.inspectionForm.aircraft_hours ? parseFloat(this.inspectionForm.aircraft_hours) : null,
                    logbook_entry: this.inspectionForm.logbook_entry_id || null,
                };

                let response;
                if (this.editingInspectionRecord) {
                    response = await fetch(`/api/inspections/${this.editingInspectionRecord.id}/`, {
                        method: 'PATCH',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
                        body: JSON.stringify(data),
                    });
                } else {
                    data.inspection_type = this.selectedInspectionType.id;
                    response = await fetch(`/api/aircraft/${this.aircraftId}/inspections/`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
                        body: JSON.stringify(data),
                    });
                }

                if (response.ok) {
                    showNotification(this.editingInspectionRecord ? 'Record updated' : 'Inspection recorded', 'success');
                    const historyType = this.selectedInspectionType || (this.inspectionHistoryOpen ? this.inspectionTypes.find(t => t.id === this.editingInspectionRecord?.inspection_type) : null);
                    this.closeInspectionModal();
                    this.inspectionsLoaded = false;
                    await this.loadInspections();
                    await this.loadData();
                    if (this.inspectionHistoryOpen && historyType) {
                        await this.openInspectionHistory(historyType);
                    }
                } else {
                    const errorData = await response.json();
                    const msg = typeof errorData === 'object'
                        ? Object.values(errorData).flat().join(', ')
                        : 'Failed to save record';
                    showNotification(msg, 'danger');
                }
            } catch (error) {
                console.error('Error saving inspection:', error);
                showNotification('Error saving inspection', 'danger');
            } finally {
                this.inspectionSubmitting = false;
            }
        },

        async openInspectionHistory(insp) {
            this.selectedInspectionType = insp;
            this.inspectionHistory = [];
            this.inspectionHistoryLoading = true;
            this.inspectionHistoryOpen = true;

            // In public view, use pre-loaded data from the public API response
            if (this.isPublicView && insp.inspection_history) {
                this.inspectionHistory = insp.inspection_history;
                this.inspectionHistoryLoading = false;
                return;
            }

            try {
                const response = await fetch(`/api/inspections/?inspection_type=${insp.id}&aircraft=${this.aircraftId}`);
                const data = await response.json();
                this.inspectionHistory = data.results || data;
            } catch (error) {
                console.error('Error loading inspection history:', error);
                showNotification('Failed to load inspection history', 'danger');
            } finally {
                this.inspectionHistoryLoading = false;
            }
        },

        closeInspectionHistory() {
            this.inspectionHistoryOpen = false;
            this.selectedInspectionType = null;
            this.inspectionHistory = [];
        },

        async deleteInspectionRecord(record) {
            if (!confirm('Delete this inspection record? This cannot be undone.')) return;
            try {
                const response = await fetch(`/api/inspections/${record.id}/`, {
                    method: 'DELETE',
                    headers: { 'X-CSRFToken': getCookie('csrftoken') },
                });
                if (response.ok || response.status === 204) {
                    showNotification('Inspection record deleted', 'success');
                    this.inspectionsLoaded = false;
                    await this.loadInspections();
                    await this.loadData();
                    if (this.selectedInspectionType) {
                        await this.openInspectionHistory(this.selectedInspectionType);
                    }
                } else {
                    showNotification('Failed to delete record', 'danger');
                }
            } catch (error) {
                console.error('Error deleting inspection record:', error);
                showNotification('Error deleting inspection record', 'danger');
            }
        },

        getInspectionStatusClass(insp) {
            switch (insp.compliance_status) {
                case 'compliant': return 'pf-m-green';
                case 'due_soon': return 'pf-m-orange';
                case 'overdue': return 'pf-m-red';
                case 'never_completed': return 'pf-m-red';
                default: return 'pf-m-grey';
            }
        },

        getInspectionStatusText(insp) {
            switch (insp.compliance_status) {
                case 'compliant': return 'Compliant';
                case 'due_soon': return 'Due Soon';
                case 'overdue': return 'Overdue';
                case 'never_completed': return 'Never Completed';
                default: return 'Unknown';
            }
        },
    };
}
