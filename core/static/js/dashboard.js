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
        }
    }
}
