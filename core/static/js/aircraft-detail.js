function aircraftDetail(aircraftId) {
    return {
        aircraftId: aircraftId,
        aircraft: null,
        components: [],
        recentLogs: [],
        activeSquawks: [],
        loading: true,
        activeTab: 'overview',

        async init() {
            await this.loadData();
        },

        async loadData() {
            this.loading = true;
            try {
                // Load aircraft summary with all related data
                const response = await fetch(`/api/aircraft/${this.aircraftId}/summary/`);
                const data = await response.json();

                this.aircraft = data.aircraft;
                this.components = data.components;
                this.recentLogs = data.recent_logs;
                this.activeSquawks = data.active_squawks;
            } catch (error) {
                console.error('Error loading aircraft data:', error);
                showNotification('Failed to load aircraft data', 'danger');
            } finally {
                this.loading = false;
            }
        },

        openHoursModal() {
            window.dispatchEvent(new CustomEvent('open-hours-modal', {
                detail: { aircraft: this.aircraft }
            }));
        },

        formatHours(hours) {
            return parseFloat(hours || 0).toFixed(1);
        },

        formatDate(dateString) {
            return new Date(dateString).toLocaleDateString();
        },

        getComponentTypeName(component) {
            return component.component_type_name || 'Unknown';
        },

        calculateHoursToTBO(component) {
            if (!component.tbo_hours) {
                return 'N/A';
            }
            const remaining = component.tbo_hours - (component.hours_since_overhaul || 0);
            return remaining > 0 ? remaining.toFixed(1) : '0.0';
        },

        getStatusClass(component) {
            if (component.status === 'IN-USE') {
                // Check if due for service
                const hoursToTBO = this.calculateHoursToTBO(component);
                if (hoursToTBO !== 'N/A') {
                    const hours = parseFloat(hoursToTBO);
                    if (hours <= 0) {
                        return 'pf-m-red'; // Overdue
                    } else if (hours < 50) {
                        return 'pf-m-orange'; // Due soon
                    }
                }
                return 'pf-m-green'; // Serviceable
            } else if (component.status === 'SPARE') {
                return 'pf-m-blue';
            } else if (component.status === 'DISPOSED') {
                return 'pf-m-red';
            }
            return 'pf-m-grey';
        }
    }
}
