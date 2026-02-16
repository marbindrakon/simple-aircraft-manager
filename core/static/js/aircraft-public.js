function publicAircraftView(shareToken) {
    return {
        shareToken,
        aircraft: null,
        components: [],
        activeSquawks: [],
        notes: [],
        recentLogs: [],
        ads: [],
        inspections: [],
        oilRecords: [],
        fuelRecords: [],
        documentCollections: [],
        documents: [],
        loading: true,
        error: null,
        activeTab: 'overview',

        async init() {
            await this.loadData();
        },

        async loadData() {
            this.loading = true;
            this.error = null;
            try {
                const resp = await fetch(`/api/shared/${this.shareToken}/`);
                if (!resp.ok) {
                    this.error = 'This shared link is no longer available.';
                    this.loading = false;
                    return;
                }
                const data = await resp.json();
                this.aircraft = data.aircraft;
                this.components = data.components || [];
                this.activeSquawks = data.active_squawks || [];
                this.notes = data.notes || [];
                this.recentLogs = data.recent_logs || [];
                this.ads = data.ads || [];
                this.inspections = data.inspections || [];
                this.oilRecords = data.oil_records || [];
                this.fuelRecords = data.fuel_records || [];
                this.documentCollections = data.document_collections || [];
                this.documents = data.documents || [];
            } catch (e) {
                this.error = 'Failed to load aircraft data.';
            }
            this.loading = false;
        },

        get hasAds() { return this.ads.length > 0; },
        get hasInspections() { return this.inspections.length > 0; },
        get hasLogbook() { return this.recentLogs.length > 0; },
        get hasDocuments() { return this.documentCollections.length > 0 || this.documents.length > 0; },

        getAdStatusClass(ad) {
            const s = ad.compliance_status;
            if (s === 'overdue' || s === 'no_compliance') return 'pf-m-red';
            if (s === 'due_soon') return 'pf-m-orange';
            if (s === 'conditional') return 'pf-m-blue';
            return 'pf-m-green';
        },

        getAdStatusText(ad) {
            const map = {
                compliant: 'Compliant',
                overdue: 'Overdue',
                due_soon: 'Due Soon',
                no_compliance: 'No Compliance',
                conditional: 'Conditional',
            };
            return map[ad.compliance_status] || ad.compliance_status || '-';
        },

        getInspectionStatusClass(insp) {
            const s = insp.compliance_status;
            if (s === 'overdue' || s === 'never_completed') return 'pf-m-red';
            if (s === 'due_soon') return 'pf-m-orange';
            return 'pf-m-green';
        },

        getInspectionStatusText(insp) {
            const map = {
                compliant: 'Compliant',
                overdue: 'Overdue',
                due_soon: 'Due Soon',
                never_completed: 'Never Done',
            };
            return map[insp.compliance_status] || insp.compliance_status || '-';
        },

        oilBurnRate() {
            // Calculate quarts per hour from recent records that have flight_hours
            const records = this.oilRecords.filter(r => r.flight_hours > 0 && r.quantity_added > 0);
            if (records.length < 2) return null;
            const totalQts = records.reduce((s, r) => s + parseFloat(r.quantity_added || 0), 0);
            const totalHrs = records.reduce((s, r) => s + parseFloat(r.flight_hours || 0), 0);
            if (totalHrs === 0) return null;
            return (totalQts / totalHrs).toFixed(3);
        },

        fuelBurnRate() {
            const records = this.fuelRecords.filter(r => r.flight_hours > 0 && r.quantity_added > 0);
            if (records.length < 2) return null;
            const totalGal = records.reduce((s, r) => s + parseFloat(r.quantity_added || 0), 0);
            const totalHrs = records.reduce((s, r) => s + parseFloat(r.flight_hours || 0), 0);
            if (totalHrs === 0) return null;
            return (totalGal / totalHrs).toFixed(1);
        },

        formatDate(dateString) {
            return formatDate(dateString);
        },
        formatHours(hours) {
            return formatHours(hours);
        },
        getAirworthinessClass(aircraft) {
            return getAirworthinessClass(aircraft);
        },
        getAirworthinessText(aircraft) {
            return getAirworthinessText(aircraft);
        },
        getSquawkPriorityClass(priority) {
            return getSquawkPriorityClass(priority);
        },
    };
}
