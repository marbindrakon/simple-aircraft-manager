function adsMixin() {
    return {
        // AD tracking state
        applicableAds: [],
        allAds: [],
        allAdsLoading: false,
        adsLoaded: false,
        adModalOpen: false,
        complianceModalOpen: false,
        selectedAd: null,
        editingAd: null,
        selectedExistingAdId: '',
        adSearchQuery: '',
        adSubmitting: false,
        complianceSubmitting: false,

        // Expandable rows
        expandedAdIds: {},

        // Document picker for AD modal
        adDocPickerQuery: '',
        adDocPickerResults: [],
        adDocPickerDropdownOpen: false,
        adDocPickerLoading: false,
        adDocPickerSelected: null,
        adDocPickerTimer: null,

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
            bulletin_type: 'ad',
            mandatory: true,
            document_id: null,
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
                ad => ad.mandatory && (ad.compliance_status === 'overdue' || ad.compliance_status === 'no_compliance')
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

        get mandatoryAds() {
            return this.sortedApplicableAds.filter(ad => ad.mandatory);
        },

        get nonMandatoryAds() {
            return this.sortedApplicableAds.filter(ad => !ad.mandatory);
        },

        get filteredAvailableAds() {
            const q = this.adSearchQuery.toLowerCase().trim();
            if (!q) return this.availableAds;
            return this.availableAds.filter(ad =>
                ad.name.toLowerCase().includes(q) ||
                ad.short_description.toLowerCase().includes(q) ||
                this.getBulletinTypeLabel(ad.bulletin_type).toLowerCase().includes(q)
            );
        },

        get selectedExistingAd() {
            if (!this.selectedExistingAdId) return null;
            return this.availableAds.find(ad => ad.id === this.selectedExistingAdId) || null;
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
            this.allAdsLoading = true;
            try {
                const response = await fetch('/api/ads/');
                const data = await response.json();
                this.allAds = data.results || data;
                return this.allAds;
            } catch (error) {
                console.error('Error loading all ADs:', error);
                return [];
            } finally {
                this.allAdsLoading = false;
            }
        },

        get availableAds() {
            const applicableIds = new Set(this.applicableAds.map(a => a.id));
            return this.allAds.filter(a => !applicableIds.has(a.id));
        },

        openAdModal() {
            this.editingAd = null;
            this.selectedExistingAdId = '';
            this.adSearchQuery = '';
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
                bulletin_type: 'ad',
                mandatory: true,
                document_id: null,
            };
            this.adDocPickerSelected = null;
            this.adDocPickerQuery = '';
            this.adDocPickerResults = [];
            this.adDocPickerDropdownOpen = false;
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
                bulletin_type: ad.bulletin_type || 'ad',
                mandatory: ad.mandatory !== undefined ? ad.mandatory : true,
                document_id: ad.document ? ad.document.id : null,
            };
            this.adDocPickerSelected = ad.document || null;
            this.adDocPickerQuery = '';
            this.adDocPickerResults = [];
            this.adDocPickerDropdownOpen = false;
            this.adModalOpen = true;
        },

        closeAdModal() {
            this.adModalOpen = false;
            this.editingAd = null;
            this.selectedExistingAdId = '';
            this.adSearchQuery = '';
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
                    showNotification('Bulletin added to aircraft', 'success');
                    this.closeAdModal();
                    this.adsLoaded = false;
                    await this.loadAds();
                    await this.loadData();
                } else {
                    const errorData = await response.json();
                    showNotification(errorData.error || 'Failed to add bulletin', 'danger');
                }
            } catch (error) {
                console.error('Error adding bulletin:', error);
                showNotification('Error adding bulletin', 'danger');
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
                    bulletin_type: this.adForm.bulletin_type,
                    mandatory: this.adForm.mandatory,
                    document_id: this.adForm.document_id || null,
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
                    showNotification('Bulletin created and added to aircraft', 'success');
                    this.closeAdModal();
                    this.adsLoaded = false;
                    await this.loadAds();
                    await this.loadData();
                } else {
                    const errorData = await response.json();
                    const msg = typeof errorData === 'object'
                        ? Object.values(errorData).flat().join(', ')
                        : 'Failed to create bulletin';
                    showNotification(msg, 'danger');
                }
            } catch (error) {
                console.error('Error creating bulletin:', error);
                showNotification('Error creating bulletin', 'danger');
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
                    bulletin_type: this.adForm.bulletin_type,
                    mandatory: this.adForm.mandatory,
                    document_id: this.adForm.document_id || null,
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
                    showNotification('Bulletin updated', 'success');
                    this.closeAdModal();
                    this.adsLoaded = false;
                    await this.loadAds();
                    await this.loadData();
                } else {
                    const errorData = await response.json();
                    const msg = typeof errorData === 'object'
                        ? Object.values(errorData).flat().join(', ')
                        : 'Failed to update bulletin';
                    showNotification(msg, 'danger');
                }
            } catch (error) {
                console.error('Error updating bulletin:', error);
                showNotification('Error updating bulletin', 'danger');
            } finally {
                this.adSubmitting = false;
            }
        },

        async removeAd(ad) {
            if (!confirm(`Remove bulletin "${ad.name}" from this aircraft?`)) return;
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
                    showNotification('Bulletin removed from aircraft', 'success');
                    this.adsLoaded = false;
                    await this.loadAds();
                    await this.loadData();
                } else {
                    showNotification('Failed to remove bulletin', 'danger');
                }
            } catch (error) {
                console.error('Error removing bulletin:', error);
                showNotification('Error removing bulletin', 'danger');
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

        toggleAdExpand(adId) {
            if (this.expandedAdIds[adId]) {
                const copy = { ...this.expandedAdIds };
                delete copy[adId];
                this.expandedAdIds = copy;
            } else {
                this.expandedAdIds = { ...this.expandedAdIds, [adId]: true };
            }
        },

        adDocPickerInput() {
            clearTimeout(this.adDocPickerTimer);
            if (!this.adDocPickerQuery.trim()) {
                this.adDocPickerResults = [];
                this.adDocPickerDropdownOpen = false;
                return;
            }
            this.adDocPickerTimer = setTimeout(() => this.adDocPickerSearch(), 300);
        },

        async adDocPickerSearch() {
            this.adDocPickerLoading = true;
            const params = new URLSearchParams({
                aircraft: this.aircraftId,
                search: this.adDocPickerQuery.trim(),
                limit: 8,
            });
            try {
                const resp = await fetch(`/api/documents/?${params}`);
                const data = await resp.json();
                this.adDocPickerResults = data.results || [];
                this.adDocPickerDropdownOpen = true;
            } catch (e) {
                console.error('Document picker search error:', e);
            } finally {
                this.adDocPickerLoading = false;
            }
        },

        adDocPickerSelect(doc) {
            this.adDocPickerSelected = doc;
            this.adForm.document_id = doc.id;
            this.adDocPickerDropdownOpen = false;
            this.adDocPickerQuery = '';
        },

        adDocPickerClear() {
            this.adDocPickerSelected = null;
            this.adForm.document_id = null;
            this.adDocPickerQuery = '';
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

        getBulletinTypeLabel(bulletinType) {
            const labels = { ad: 'AD', saib: 'SAIB', sb: 'Service Bulletin', alert: 'Airworthiness Alert', other: 'Other' };
            return labels[bulletinType] || bulletinType || 'AD';
        },

        getBulletinTypeClass(bulletinType) {
            return bulletinType === 'ad' ? 'pf-m-red' : 'pf-m-blue';
        },
    };
}
