function aircraftDetail(aircraftId) {
    return mergeMixins(
        // Feature mixins (order doesn't matter — all end up on one object)
        componentsMixin(),
        squawksMixin(),
        notesMixin(),
        oilMixin(),
        fuelMixin(),
        logbookMixin(),
        adsMixin(),
        inspectionsMixin(),
        documentsMixin(),
        eventsMixin(),
        rolesMixin(),

        // Core state and methods (last so they win on any key collision)
        {
            aircraftId: aircraftId,
            aircraft: null,
            components: [],
            recentLogs: [],
            activeSquawks: [],
            loading: true,
            activeTab: 'overview',

            // Role-based access helpers
            get userRole() { return this.aircraft?.user_role || null; },
            get isOwner() { return this.userRole === 'owner' || this.userRole === 'admin'; },
            get isPilot() { return this.userRole === 'pilot'; },
            get canWrite() { return this.isOwner; },
            get canUpdateHours() { return this.isOwner || this.isPilot; },
            get canCreateSquawk() { return this.isOwner || this.isPilot; },
            get canCreateConsumable() { return this.isOwner || this.isPilot; },
            get canCreateNote() { return this.isOwner || this.isPilot; },

            async init() {
                await this.loadData();

                // Load ADs and inspections eagerly so issue count badges are visible immediately
                this.loadAds();
                this.loadInspections();

                // Watch for tab changes to load data lazily
                this.$watch('activeTab', (tab) => {
                    if (tab === 'logbook' && !this.logbookLoaded) {
                        this.loadLogbookEntries();
                    }
                    if (tab === 'documents' && !this.documentsLoaded) {
                        this.loadDocuments();
                    }
                    if (tab === 'oil' && !this.oilLoaded) {
                        this.loadOilRecords();
                    }
                    if (tab === 'fuel' && !this.fuelLoaded) {
                        this.loadFuelRecords();
                    }
                    if (tab === 'inspections' && !this.inspectionsLoaded) {
                        this.loadInspections();
                    }
                    if (tab === 'roles' && !this.rolesLoaded) {
                        this.loadRoles();
                    }
                });
            },

            async loadData() {
                this.loading = true;
                try {
                    const response = await fetch(`/api/aircraft/${this.aircraftId}/summary/`);
                    const data = await response.json();

                    this.aircraft = data.aircraft;
                    this.components = data.components;
                    this.recentLogs = data.recent_logs;
                    this.activeSquawks = data.active_squawks;
                    this.aircraftNotes = data.notes || [];

                    // Init sharing state from aircraft data
                    this.initSharingState();

                    // Refresh recent events (non-blocking)
                    this.loadRecentEvents();
                } catch (error) {
                    console.error('Error loading aircraft data:', error);
                    showNotification('Failed to load aircraft data', 'danger');
                } finally {
                    this.loading = false;
                }
            },

            // Shared utility delegators
            formatHours(hours) { return formatHours(hours); },
            formatDate(dateString) { return formatDate(dateString); },
            formatDateTime(dateString) { return new Date(dateString).toLocaleString(); },

            extractIdFromUrl(url) {
                if (!url) return null;
                const match = url.match(/\/([0-9a-f-]{36})\/?$/i);
                return match ? match[1] : null;
            },

            // Airworthiness helpers
            getAirworthinessClass() {
                return getAirworthinessClass(this.aircraft?.airworthiness?.status || 'GREEN');
            },

            getAirworthinessText() {
                return getAirworthinessText(this.aircraft?.airworthiness?.status || 'GREEN');
            },

            getAirworthinessTooltip() {
                return getAirworthinessTooltip(this.aircraft?.airworthiness);
            },

            // Hours modal
            openHoursModal() {
                window.dispatchEvent(new CustomEvent('open-hours-modal', {
                    detail: { aircraft: this.aircraft }
                }));
            },

            // Aircraft edit/delete (delegates to aircraft-modal.js via events)
            openEditModal() {
                window.dispatchEvent(new CustomEvent('open-aircraft-modal', {
                    detail: { aircraft: this.aircraft }
                }));
            },

            openDeleteModal() {
                window.dispatchEvent(new CustomEvent('open-aircraft-delete-modal', {
                    detail: { aircraft: this.aircraft }
                }));
            },
        }
    );
}
