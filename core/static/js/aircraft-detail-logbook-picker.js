function logbookPickerMixin() {
    return {
        // Picker state — shared across all three record modals (only one open at a time)
        pickerTargetForm: null,      // 'complianceForm' | 'inspectionForm' | 'majorRecordForm'
        pickerTargetField: null,     // 'logbook_entry_id' | 'logbook_entry'
        pickerSearchQuery: '',
        pickerSearchResults: [],
        pickerDropdownOpen: false,
        pickerSearchLoading: false,
        pickerSelectedEntry: null,   // full entry object for chip display
        pickerSearchTimer: null,

        // Browse modal state
        pickerBrowseOpen: false,
        pickerBrowseSearch: '',
        pickerBrowseLogType: '',
        pickerBrowseEntryType: '',
        pickerBrowseResults: [],
        pickerBrowseTotal: 0,
        pickerBrowseLoading: false,
        pickerBrowseSearchTimer: null,
        pickerBrowseOffset: 0,

        get pickerBrowseHasMore() {
            return this.pickerBrowseResults.length < this.pickerBrowseTotal;
        },

        // Called at modal open. Resets all picker state, sets target, loads existing entry if editing.
        async pickerInit(targetForm, targetField, existingId) {
            this.pickerTargetForm = targetForm;
            this.pickerTargetField = targetField;
            this.pickerSearchQuery = '';
            this.pickerSearchResults = [];
            this.pickerDropdownOpen = false;
            this.pickerSearchLoading = false;
            this.pickerSelectedEntry = null;
            this.pickerBrowseOpen = false;
            clearTimeout(this.pickerSearchTimer);

            if (existingId) {
                await this.pickerLoadById(existingId);
            }
        },

        // Load an existing entry for chip display. Checks logbookEntries cache first.
        async pickerLoadById(id) {
            if (!id) return;
            // Check cache first
            const cached = (this.logbookEntries || []).find(e => e.id === id);
            if (cached) {
                this.pickerSelectedEntry = cached;
                return;
            }
            try {
                const response = await fetch(`/api/logbook-entries/${id}/`);
                if (response.ok) {
                    this.pickerSelectedEntry = await response.json();
                }
            } catch (error) {
                console.error('Error loading logbook entry for picker:', error);
            }
        },

        // Debounced input handler for the search field.
        pickerOnInput() {
            clearTimeout(this.pickerSearchTimer);
            if (!this.pickerSearchQuery.trim()) {
                this.pickerDropdownOpen = false;
                this.pickerSearchResults = [];
                return;
            }
            this.pickerSearchTimer = setTimeout(() => this.pickerDoSearch(), 300);
        },

        async pickerDoSearch() {
            if (!this.pickerSearchQuery.trim()) return;
            this.pickerSearchLoading = true;
            this.pickerDropdownOpen = true;
            try {
                const params = new URLSearchParams({
                    aircraft: this.aircraftId,
                    search: this.pickerSearchQuery.trim(),
                    limit: 8,
                });
                const response = await fetch(`/api/logbook-entries/?${params}`);
                const data = await response.json();
                this.pickerSearchResults = data.results || [];
            } catch (error) {
                console.error('Error searching logbook entries:', error);
                this.pickerSearchResults = [];
            } finally {
                this.pickerSearchLoading = false;
            }
        },

        // Select an entry: write its ID to the target form field and show chip.
        // Also pre-fills date and hours in the compliance / inspection forms (Flow B).
        pickerSelectEntry(entry) {
            this.pickerSelectedEntry = entry;
            if (this.pickerTargetForm && this.pickerTargetField) {
                this[this.pickerTargetForm][this.pickerTargetField] = entry.id;
            }

            // Pre-fill date and hours for compliance / inspection modals
            if (this.pickerTargetForm === 'complianceForm') {
                if (entry.date) this.complianceForm.date_complied = entry.date;
                if (entry.aircraft_hours_at_entry != null) {
                    const hrs = parseFloat(entry.aircraft_hours_at_entry);
                    this.complianceForm.aircraft_hours = hrs.toFixed(1);
                    // Recompute next_due_at_time for recurring ADs
                    if (this.selectedAd && this.selectedAd.recurring && this.selectedAd.recurring_hours > 0) {
                        this.complianceForm.next_due_at_time = (
                            hrs + parseFloat(this.selectedAd.recurring_hours)
                        ).toFixed(1);
                    }
                }
                // Pre-fill compliance notes if the field is still empty
                if (!this.complianceForm.compliance_notes && entry.text) {
                    this.complianceForm.compliance_notes = entry.text;
                }
            } else if (this.pickerTargetForm === 'inspectionForm') {
                if (entry.date) this.inspectionForm.date = entry.date;
                if (entry.aircraft_hours_at_entry != null) {
                    this.inspectionForm.aircraft_hours = parseFloat(entry.aircraft_hours_at_entry).toFixed(1);
                }
            }

            this.pickerDropdownOpen = false;
            this.pickerBrowseOpen = false;
            this.pickerSearchQuery = '';
        },

        // Clear the selected entry and reset the form field.
        pickerClear() {
            this.pickerSelectedEntry = null;
            if (this.pickerTargetForm && this.pickerTargetField) {
                this[this.pickerTargetForm][this.pickerTargetField] = '';
            }
        },

        // Open the browse modal and load initial results.
        pickerOpenBrowse() {
            this.pickerBrowseSearch = '';
            this.pickerBrowseLogType = '';
            this.pickerBrowseEntryType = '';
            this.pickerBrowseResults = [];
            this.pickerBrowseTotal = 0;
            this.pickerBrowseOffset = 0;
            this.pickerBrowseOpen = true;
            this.pickerBrowseLoad(false);
        },

        async pickerBrowseLoad(append) {
            if (!append) {
                this.pickerBrowseOffset = 0;
            }
            this.pickerBrowseLoading = true;
            try {
                const params = new URLSearchParams({
                    aircraft: this.aircraftId,
                    limit: 10,
                    offset: this.pickerBrowseOffset,
                });
                if (this.pickerBrowseSearch.trim()) params.set('search', this.pickerBrowseSearch.trim());
                if (this.pickerBrowseLogType) params.set('log_type', this.pickerBrowseLogType);
                if (this.pickerBrowseEntryType) params.set('entry_type', this.pickerBrowseEntryType);
                const response = await fetch(`/api/logbook-entries/?${params}`);
                const data = await response.json();
                const newResults = data.results || [];
                this.pickerBrowseTotal = data.count ?? 0;
                if (append) {
                    this.pickerBrowseResults = [...this.pickerBrowseResults, ...newResults];
                } else {
                    this.pickerBrowseResults = newResults;
                }
                this.pickerBrowseOffset = this.pickerBrowseResults.length;
            } catch (error) {
                console.error('Error loading logbook entries for browse:', error);
            } finally {
                this.pickerBrowseLoading = false;
            }
        },

        // Debounced filter change handler for text input in browse modal.
        pickerBrowseApplyFilters() {
            clearTimeout(this.pickerBrowseSearchTimer);
            this.pickerBrowseSearchTimer = setTimeout(() => this.pickerBrowseLoad(false), 300);
        },

        // Immediate filter change handler for select dropdowns in browse modal.
        pickerBrowseApplyFiltersImmediate() {
            clearTimeout(this.pickerBrowseSearchTimer);
            this.pickerBrowseLoad(false);
        },

        pickerBrowseLoadMore() {
            this.pickerBrowseLoad(true);
        },
    };
}
