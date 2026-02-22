function adsMixin() {
    return {
        // AD tracking state
        applicableAds: [],
        allAds: [],
        adsLoaded: false,
        adModalOpen: false,
        complianceModalOpen: false,
        selectedAd: null,
        editingAd: null,
        selectedExistingAdId: '',
        adSubmitting: false,
        complianceSubmitting: false,
        adForm: {
            name: '',
            short_description: '',
            required_action: '',
            compliance_type: 'standard',
            trigger_condition: '',
            recurring: false,
            recurring_hours: 0,
            recurring_months: 0,
            recurring_days: 0,
        },
        editingComplianceRecord: null,
        complianceForm: {
            date_complied: '',
            compliance_notes: '',
            permanent: false,
            next_due_at_time: '',
            aircraft_hours: '',
            logbook_entry_id: '',
        },

        // Compliance history state
        complianceHistoryOpen: false,
        selectedAdForHistory: null,
        complianceHistory: [],
        complianceHistoryLoading: false,

        // Logbook entry detail (view from compliance history)
        logEntryDetailOpen: false,
        logEntryDetail: null,
        logEntryDetailLoading: false,
        logEntryImageIndex: 0,
        relatedDocImageIndices: {},

        get adIssueCount() {
            return this.applicableAds.filter(
                ad => ad.compliance_status === 'overdue' || ad.compliance_status === 'no_compliance'
            ).length;
        },

        get sortedApplicableAds() {
            function adSortKey(name) {
                // Normalize leading 2-digit year (1900s) to 4 digits for correct ordering
                // e.g. "98-12-03" → "1998-12-03", "2024-01-05" unchanged
                return name.replace(/^(\d{2})(?!\d)-/, '19$1-');
            }
            return [...this.applicableAds].sort((a, b) => adSortKey(a.name).localeCompare(adSortKey(b.name)));
        },

        async loadAds() {
            try {
                const response = await fetch(`/api/aircraft/${this.aircraftId}/ads/`);
                const data = await response.json();
                this.applicableAds = data.ads || [];
                this.adsLoaded = true;
            } catch (error) {
                console.error('Error loading ADs:', error);
                showNotification('Failed to load ADs', 'danger');
            }
        },

        async loadAllAds() {
            try {
                const response = await fetch('/api/ads/');
                const data = await response.json();
                this.allAds = data.results || data;
                return this.allAds;
            } catch (error) {
                console.error('Error loading all ADs:', error);
                return [];
            }
        },

        get availableAds() {
            const applicableIds = new Set(this.applicableAds.map(a => a.id));
            return this.allAds.filter(a => !applicableIds.has(a.id));
        },

        openAdModal() {
            this.editingAd = null;
            this.selectedExistingAdId = '';
            this.adForm = {
                name: '',
                short_description: '',
                required_action: '',
                compliance_type: 'standard',
                trigger_condition: '',
                recurring: false,
                recurring_hours: 0,
                recurring_months: 0,
                recurring_days: 0,
            };
            this.loadAllAds();
            this.adModalOpen = true;
        },

        editAd(ad) {
            this.editingAd = ad;
            this.selectedExistingAdId = '';
            this.adForm = {
                name: ad.name,
                short_description: ad.short_description,
                required_action: ad.required_action || '',
                compliance_type: ad.compliance_type || 'standard',
                trigger_condition: ad.trigger_condition || '',
                recurring: ad.recurring,
                recurring_hours: ad.recurring_hours || 0,
                recurring_months: ad.recurring_months || 0,
                recurring_days: ad.recurring_days || 0,
            };
            this.adModalOpen = true;
        },

        closeAdModal() {
            this.adModalOpen = false;
            this.editingAd = null;
        },

        async addExistingAd() {
            if (!this.selectedExistingAdId || this.adSubmitting) return;
            this.adSubmitting = true;
            try {
                const response = await fetch(`/api/aircraft/${this.aircraftId}/ads/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                    body: JSON.stringify({ ad_id: this.selectedExistingAdId }),
                });

                if (response.ok) {
                    showNotification('AD added to aircraft', 'success');
                    this.closeAdModal();
                    this.adsLoaded = false;
                    await this.loadAds();
                    await this.loadData();
                } else {
                    const errorData = await response.json();
                    showNotification(errorData.error || 'Failed to add AD', 'danger');
                }
            } catch (error) {
                console.error('Error adding AD:', error);
                showNotification('Error adding AD', 'danger');
            } finally {
                this.adSubmitting = false;
            }
        },

        async createAndAddAd() {
            if (!this.adForm.name || !this.adForm.short_description || this.adSubmitting) return;
            this.adSubmitting = true;
            try {
                const data = {
                    name: this.adForm.name,
                    short_description: this.adForm.short_description,
                    required_action: this.adForm.required_action,
                    compliance_type: this.adForm.compliance_type,
                    trigger_condition: this.adForm.compliance_type === 'conditional' ? this.adForm.trigger_condition : '',
                    recurring: this.adForm.recurring,
                    recurring_hours: this.adForm.recurring ? parseFloat(this.adForm.recurring_hours) || 0 : 0,
                    recurring_months: this.adForm.recurring ? parseInt(this.adForm.recurring_months) || 0 : 0,
                    recurring_days: this.adForm.recurring ? parseInt(this.adForm.recurring_days) || 0 : 0,
                };

                const response = await fetch(`/api/aircraft/${this.aircraftId}/ads/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                    body: JSON.stringify(data),
                });

                if (response.ok) {
                    showNotification('AD created and added to aircraft', 'success');
                    this.closeAdModal();
                    this.adsLoaded = false;
                    await this.loadAds();
                    await this.loadData();
                } else {
                    const errorData = await response.json();
                    const msg = typeof errorData === 'object'
                        ? Object.values(errorData).flat().join(', ')
                        : 'Failed to create AD';
                    showNotification(msg, 'danger');
                }
            } catch (error) {
                console.error('Error creating AD:', error);
                showNotification('Error creating AD', 'danger');
            } finally {
                this.adSubmitting = false;
            }
        },

        async updateAd() {
            if (!this.adForm.name || !this.adForm.short_description || this.adSubmitting) return;
            this.adSubmitting = true;
            try {
                const data = {
                    name: this.adForm.name,
                    short_description: this.adForm.short_description,
                    required_action: this.adForm.required_action,
                    compliance_type: this.adForm.compliance_type,
                    trigger_condition: this.adForm.compliance_type === 'conditional' ? this.adForm.trigger_condition : '',
                    recurring: this.adForm.recurring,
                    recurring_hours: this.adForm.recurring ? parseFloat(this.adForm.recurring_hours) || 0 : 0,
                    recurring_months: this.adForm.recurring ? parseInt(this.adForm.recurring_months) || 0 : 0,
                    recurring_days: this.adForm.recurring ? parseInt(this.adForm.recurring_days) || 0 : 0,
                };

                const response = await fetch(`/api/ads/${this.editingAd.id}/`, {
                    method: 'PATCH',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                    body: JSON.stringify(data),
                });

                if (response.ok) {
                    showNotification('AD updated', 'success');
                    this.closeAdModal();
                    this.adsLoaded = false;
                    await this.loadAds();
                    await this.loadData();
                } else {
                    const errorData = await response.json();
                    const msg = typeof errorData === 'object'
                        ? Object.values(errorData).flat().join(', ')
                        : 'Failed to update AD';
                    showNotification(msg, 'danger');
                }
            } catch (error) {
                console.error('Error updating AD:', error);
                showNotification('Error updating AD', 'danger');
            } finally {
                this.adSubmitting = false;
            }
        },

        async removeAd(ad) {
            if (!confirm(`Remove AD "${ad.name}" from this aircraft?`)) return;
            try {
                const response = await fetch(`/api/aircraft/${this.aircraftId}/remove_ad/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                    body: JSON.stringify({ ad_id: ad.id }),
                });

                if (response.ok) {
                    showNotification('AD removed from aircraft', 'success');
                    this.adsLoaded = false;
                    await this.loadAds();
                    await this.loadData();
                } else {
                    showNotification('Failed to remove AD', 'danger');
                }
            } catch (error) {
                console.error('Error removing AD:', error);
                showNotification('Error removing AD', 'danger');
            }
        },

        openComplianceModal(ad) {
            this.editingComplianceRecord = null;
            this.selectedAd = ad;
            this.complianceForm = {
                date_complied: new Date().toISOString().split('T')[0],
                compliance_notes: '',
                permanent: false,
                next_due_at_time: '',
                aircraft_hours: this.aircraft ? parseFloat(this.aircraft.flight_time || 0).toFixed(1) : '',
                logbook_entry_id: '',
            };
            if (ad.recurring && ad.recurring_hours > 0 && this.aircraft) {
                this.complianceForm.next_due_at_time = (
                    parseFloat(this.aircraft.flight_time) + parseFloat(ad.recurring_hours)
                ).toFixed(1);
            }
            this.pickerInit('complianceForm', 'logbook_entry_id', '');
            this.complianceModalOpen = true;
        },

        async openEditComplianceModal(record) {
            this.editingComplianceRecord = record;
            this.selectedAd = this.selectedAdForHistory;
            const existingId = record.logbook_entry ? this.extractIdFromUrl(record.logbook_entry) : '';
            this.complianceForm = {
                date_complied: record.date_complied,
                compliance_notes: record.compliance_notes || '',
                permanent: record.permanent,
                next_due_at_time: record.next_due_at_time || '',
                aircraft_hours: record.aircraft_hours_at_compliance || '',
                logbook_entry_id: existingId,
            };
            await this.pickerInit('complianceForm', 'logbook_entry_id', existingId);
            this.complianceModalOpen = true;
        },

        closeComplianceModal() {
            this.complianceModalOpen = false;
            this.pickerBrowseOpen = false;
            this.selectedAd = null;
            this.editingComplianceRecord = null;
        },

        async submitCompliance() {
            if (this.complianceSubmitting || !this.selectedAd) return;
            this.complianceSubmitting = true;
            try {
                const data = {
                    date_complied: this.complianceForm.date_complied,
                    compliance_notes: this.complianceForm.compliance_notes,
                    permanent: this.complianceForm.permanent,
                    next_due_at_time: this.complianceForm.permanent ? 0 : (parseFloat(this.complianceForm.next_due_at_time) || 0),
                    aircraft_hours_at_compliance: this.complianceForm.aircraft_hours ? parseFloat(this.complianceForm.aircraft_hours) : null,
                    logbook_entry: this.complianceForm.logbook_entry_id || null,
                };

                let response;
                if (this.editingComplianceRecord) {
                    response = await fetch(`/api/ad-compliances/${this.editingComplianceRecord.id}/`, {
                        method: 'PATCH',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
                        body: JSON.stringify(data),
                    });
                } else {
                    data.ad = this.selectedAd.id;
                    response = await fetch(`/api/aircraft/${this.aircraftId}/compliance/`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
                        body: JSON.stringify(data),
                    });
                }

                if (response.ok) {
                    showNotification(this.editingComplianceRecord ? 'Compliance updated' : 'Compliance recorded', 'success');
                    const wasEditing = !!this.editingComplianceRecord;
                    this.closeComplianceModal();
                    this.adsLoaded = false;
                    await this.loadAds();
                    await this.loadData();
                    if (wasEditing && this.complianceHistoryOpen && this.selectedAdForHistory) {
                        await this.openComplianceHistory(this.selectedAdForHistory);
                    }
                } else {
                    const errorData = await response.json();
                    const msg = typeof errorData === 'object'
                        ? Object.values(errorData).flat().join(', ')
                        : 'Failed to save compliance record';
                    showNotification(msg, 'danger');
                }
            } catch (error) {
                console.error('Error saving compliance:', error);
                showNotification('Error saving compliance', 'danger');
            } finally {
                this.complianceSubmitting = false;
            }
        },

        async deleteComplianceRecord(record) {
            if (!confirm('Delete this compliance record? This cannot be undone.')) return;
            try {
                const response = await fetch(`/api/ad-compliances/${record.id}/`, {
                    method: 'DELETE',
                    headers: { 'X-CSRFToken': getCookie('csrftoken') },
                });
                if (response.ok || response.status === 204) {
                    showNotification('Compliance record deleted', 'success');
                    this.adsLoaded = false;
                    await this.loadAds();
                    await this.loadData();
                    if (this.selectedAdForHistory) {
                        await this.openComplianceHistory(this.selectedAdForHistory);
                    }
                } else {
                    showNotification('Failed to delete compliance record', 'danger');
                }
            } catch (error) {
                console.error('Error deleting compliance record:', error);
                showNotification('Error deleting compliance record', 'danger');
            }
        },

        async openComplianceHistory(ad) {
            this.selectedAdForHistory = ad;
            this.complianceHistory = [];
            this.complianceHistoryLoading = true;
            this.complianceHistoryOpen = true;

            // In public view, use pre-loaded data from the public API response
            if (this.isPublicView && ad.compliance_history) {
                this.complianceHistory = ad.compliance_history;
                this.complianceHistoryLoading = false;
                return;
            }

            try {
                const response = await fetch(`/api/ad-compliances/?ad=${ad.id}&aircraft=${this.aircraftId}`);
                const data = await response.json();
                this.complianceHistory = data.results || data;
            } catch (error) {
                console.error('Error loading compliance history:', error);
                showNotification('Failed to load compliance history', 'danger');
            } finally {
                this.complianceHistoryLoading = false;
            }
        },

        closeComplianceHistory() {
            this.complianceHistoryOpen = false;
            this.selectedAdForHistory = null;
            this.complianceHistory = [];
        },

        async viewLogEntryFromCompliance(logbookEntryRef) {
            // logbookEntryRef may be a URL (from HyperlinkedSerializer) or a UUID (from ModelSerializer in public API)
            const entryId = this.extractIdFromUrl(logbookEntryRef) || logbookEntryRef;
            if (!entryId) return;

            // In public view, look up from the pre-fetched linked-entries dict
            if (this.isPublicView) {
                const entry = this.linkedLogbookEntriesById?.[entryId];
                if (entry) {
                    this.logEntryDetail = entry;
                    this.logEntryImageIndex = (entry.page_number || 1) - 1;
                    this.relatedDocImageIndices = Object.fromEntries(
                        (entry.related_documents_detail || []).map(d => [d.id, 0])
                    );
                    this.logEntryDetailOpen = true;
                } else {
                    showNotification('Logbook entry not available in shared view', 'warning');
                }
                return;
            }

            this.logEntryDetailLoading = true;
            this.logEntryDetail = null;
            this.logEntryDetailOpen = true;

            try {
                const response = await fetch(`/api/logbook-entries/${entryId}/`);
                if (response.ok) {
                    this.logEntryDetail = await response.json();
                    this.logEntryImageIndex = (this.logEntryDetail.page_number || 1) - 1;
                    this.relatedDocImageIndices = Object.fromEntries(
                        (this.logEntryDetail.related_documents_detail || []).map(d => [d.id, 0])
                    );
                } else {
                    showNotification('Failed to load logbook entry', 'danger');
                    this.logEntryDetailOpen = false;
                }
            } catch (error) {
                console.error('Error loading logbook entry:', error);
                showNotification('Error loading logbook entry', 'danger');
                this.logEntryDetailOpen = false;
            } finally {
                this.logEntryDetailLoading = false;
            }
        },

        closeLogEntryDetail() {
            this.logEntryDetailOpen = false;
            this.logEntryDetail = null;
            this.logEntryImageIndex = 0;
            this.relatedDocImageIndices = {};
        },

        getAdStatusClass(ad) {
            switch (ad.compliance_status) {
                case 'compliant': return 'pf-m-green';
                case 'due_soon': return 'pf-m-orange';
                case 'overdue': return 'pf-m-red';
                case 'no_compliance': return 'pf-m-red';
                case 'conditional': return 'pf-m-blue';
                default: return 'pf-m-grey';
            }
        },

        getAdStatusText(ad) {
            switch (ad.compliance_status) {
                case 'compliant': return 'Compliant';
                case 'due_soon': return 'Due Soon';
                case 'overdue': return 'Overdue';
                case 'no_compliance': return 'No Compliance';
                case 'conditional': return 'Conditional';
                default: return 'Unknown';
            }
        },
    };
}
