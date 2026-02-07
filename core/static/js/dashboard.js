function aircraftDashboard() {
    return {
        aircraftList: [],
        loading: true,

        async init() {
            await this.loadAircraft();
        },

        async loadAircraft() {
            this.loading = true;
            try {
                const response = await fetch('/api/aircraft/');
                const data = await response.json();
                this.aircraftList = data.results || data;
            } catch (error) {
                console.error('Error loading aircraft:', error);
                showNotification('Failed to load aircraft', 'danger');
            } finally {
                this.loading = false;
            }
        },

        openHoursModal(aircraft) {
            // Trigger hours update modal
            window.dispatchEvent(new CustomEvent('open-hours-modal', {
                detail: { aircraft }
            }));
        },

        formatHours(hours) {
            return parseFloat(hours || 0).toFixed(1);
        },

        // Airworthiness status helpers
        getAirworthinessClass(aircraft) {
            const status = aircraft.airworthiness?.status || 'GREEN';
            switch (status) {
                case 'RED':
                    return 'airworthiness-red';
                case 'ORANGE':
                    return 'airworthiness-orange';
                default:
                    return 'airworthiness-green';
            }
        },

        getAirworthinessText(aircraft) {
            const status = aircraft.airworthiness?.status || 'GREEN';
            switch (status) {
                case 'RED':
                    return 'Grounded';
                case 'ORANGE':
                    return 'Caution';
                default:
                    return 'Airworthy';
            }
        },

        getAirworthinessTooltip(aircraft) {
            const aw = aircraft.airworthiness;
            if (!aw || aw.status === 'GREEN') {
                return 'Aircraft is airworthy';
            }

            const issues = aw.issues || [];
            if (issues.length === 0) {
                return aw.status === 'RED' ? 'Aircraft is grounded' : 'Maintenance due soon';
            }

            return issues.map(i => `${i.category}: ${i.title}`).join('\n');
        },

        getCardBorderClass(aircraft) {
            const status = aircraft.airworthiness?.status || 'GREEN';
            switch (status) {
                case 'RED':
                    return 'card-border-red';
                case 'ORANGE':
                    return 'card-border-orange';
                default:
                    return '';
            }
        }
    }
}
