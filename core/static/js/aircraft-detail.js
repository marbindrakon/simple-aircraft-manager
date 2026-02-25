function aircraftDetail(aircraftId, shareToken, privilegeLevel) {
    return mergeMixins(
        // Feature mixins (order doesn't matter — all end up on one object)
        componentsMixin(),
        squawksMixin(),
        notesMixin(),
        oilMixin(),
        fuelMixin(),
        logbookMixin(),
        logbookPickerMixin(),
        logbookLinkMixin(),
        adsMixin(),
        inspectionsMixin(),
        majorRecordsMixin(),
        documentsMixin(),
        eventsMixin(),
        rolesMixin(),

        // Core state and methods (last so they win on any key collision)
        {
            aircraftId: aircraftId,
            _publicShareToken: shareToken || null,
            _privilegeLevel: privilegeLevel || null,
            aircraft: null,
            components: [],
            recentLogs: [],
            linkedLogbookEntriesById: {},
            activeSquawks: [],
            resolvedSquawks: [],
            loading: true,
            activeTab: 'overview',

            // Public view detection
            get isPublicView() { return !!this._publicShareToken; },

            // Privilege level: true when private view OR maintenance privilege
            get isMaintenance() { return !this.isPublicView || this._privilegeLevel === 'maintenance'; },

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

                if (this.isPublicView) {
                    // Public mode: lazy-load logbook tab and render charts on tab activation
                    this.$watch('activeTab', (tab) => {
                        if (tab === 'logbook' && !this.logbookLoaded && this.isMaintenance) {
                            this.loadLogbookEntries();
                        }
                        if (tab === 'oil' && this.oilRecords.length >= 2) {
                            this.$nextTick(() => this.renderOilChart());
                        }
                        if (tab === 'fuel' && this.fuelRecords.length >= 2) {
                            this.$nextTick(() => this.renderFuelChart());
                        }
                    });
                    return;
                }

                // Private mode: load ADs and inspections eagerly for issue count badges
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
                    if (tab === 'major-records' && !this.majorRecordsLoaded) {
                        this.loadMajorRecords();
                    }
                    if (tab === 'roles' && !this.rolesLoaded) {
                        this.loadRoles();
                    }
                });
            },

            async loadData() {
                this.loading = true;
                try {
                    if (this.isPublicView) {
                        await this._loadPublicData();
                    } else {
                        await this._loadPrivateData();
                    }
                } catch (error) {
                    console.error('Error loading aircraft data:', error);
                    showNotification('Failed to load aircraft data', 'danger');
                } finally {
                    this.loading = false;
                }
            },

            async _loadPrivateData() {
                const response = await fetch(`/api/aircraft/${this.aircraftId}/summary/`);
                const data = await response.json();

                this.aircraft = data.aircraft;
                this.components = data.components;
                this.recentLogs = data.recent_logs;
                this.activeSquawks = data.active_squawks;
                this.aircraftNotes = data.notes || [];

                // Refresh recent events (non-blocking)
                this.loadRecentEvents();
            },

            async _loadPublicData() {
                const resp = await fetch(`/api/shared/${this._publicShareToken}/`);
                if (!resp.ok) {
                    showNotification('This shared link is no longer available.', 'danger');
                    return;
                }
                const data = await resp.json();

                this.aircraft = data.aircraft;
                this.components = data.components || [];
                this.activeSquawks = data.active_squawks || [];
                this.resolvedSquawks = data.resolved_squawks || [];
                this.aircraftNotes = data.notes || [];

                // Populate mixin state from the single public API response
                this.applicableAds = data.ads || [];
                this.adsLoaded = true;

                this.inspectionTypes = data.inspections || [];
                this.inspectionsLoaded = true;

                this.oilRecords = data.oil_records || [];
                this.oilLoaded = true;

                this.fuelRecords = data.fuel_records || [];
                this.fuelLoaded = true;

                this.documentCollections = data.document_collections || [];
                this.uncollectedDocuments = data.documents || [];
                this.documentsLoaded = true;

                // Build a fast-lookup dict for "View Logbook Entry" links on major
                // records, AD compliances, and inspections. Only the referenced entries
                // are included — the logbook tab itself lazy-loads via the paginated endpoint.
                this.linkedLogbookEntriesById = Object.fromEntries(
                    (data.linked_logbook_entries || []).map(e => [e.id, e])
                );
                // logbookLoaded stays false so the tab watcher triggers the load

                this.majorRecords = data.major_records || [];
                this.majorRecordsLoaded = true;

                this.rolesLoaded = true;
                this.eventsLoaded = true;
            },

            // Shared utility delegators
            formatHours(hours) { return formatHours(hours); },
            formatDate(dateString) { return formatDate(dateString); },
            formatDateTime(dateString) {
                return new Date(dateString).toLocaleString('default', {
                    year: 'numeric', month: 'numeric', day: 'numeric',
                    hour: 'numeric', minute: '2-digit'
                });
            },

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
