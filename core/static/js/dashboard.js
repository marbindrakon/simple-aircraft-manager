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
                const { ok, data } = await apiRequest('/api/aircraft/');
                if (ok) {
                    this.aircraftList = data.results || data;
                } else {
                    showNotification('Failed to load aircraft', 'danger');
                }
            } catch (error) {
                console.error('Error loading aircraft:', error);
                showNotification('Failed to load aircraft', 'danger');
            } finally {
                this.loading = false;
            }
        },

        openHoursModal(aircraft) {
            window.dispatchEvent(new CustomEvent('open-hours-modal', {
                detail: { aircraft }
            }));
        },

        formatHours(hours) { return formatHours(hours); },

        getAirworthinessClass(aircraft) {
            return getAirworthinessClass(aircraft.airworthiness?.status || 'GREEN');
        },

        getAirworthinessText(aircraft) {
            return getAirworthinessText(aircraft.airworthiness?.status || 'GREEN');
        },

        getAirworthinessTooltip(aircraft) {
            return getAirworthinessTooltip(aircraft.airworthiness);
        },

        getCardBorderClass(aircraft) {
            const status = aircraft.airworthiness?.status || 'GREEN';
            switch (status) {
                case 'RED': return 'card-border-red';
                case 'ORANGE': return 'card-border-orange';
                default: return '';
            }
        },

        canUpdateHours(aircraft) {
            const role = aircraft.user_role;
            return role === 'owner' || role === 'admin' || role === 'pilot';
        },
    }
}
