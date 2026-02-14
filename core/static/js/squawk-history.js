function squawkHistory(aircraftId) {
    return {
        aircraftId: aircraftId,
        aircraft: null,
        resolvedSquawks: [],
        loading: true,

        async init() {
            await this.loadData();
        },

        async loadData() {
            this.loading = true;
            try {
                const [aircraftRes, squawksRes] = await Promise.all([
                    apiRequest(`/api/aircraft/${this.aircraftId}/`),
                    apiRequest(`/api/aircraft/${this.aircraftId}/squawks/?resolved=true`)
                ]);

                if (aircraftRes.ok) {
                    this.aircraft = aircraftRes.data;
                }
                if (squawksRes.ok) {
                    this.resolvedSquawks = squawksRes.data.squawks || [];
                }
            } catch (error) {
                console.error('Error loading data:', error);
                showNotification('Failed to load squawk history', 'danger');
            } finally {
                this.loading = false;
            }
        },

        async reopenSquawk(squawk) {
            if (!confirm('Reopen this squawk?')) return;

            try {
                const { ok } = await apiRequest(`/api/squawks/${squawk.id}/`, {
                    method: 'PATCH',
                    body: JSON.stringify({ resolved: false }),
                });

                if (ok) {
                    showNotification('Squawk reopened', 'success');
                    await this.loadData();
                } else {
                    showNotification('Failed to reopen squawk', 'danger');
                }
            } catch (error) {
                console.error('Error reopening squawk:', error);
                showNotification('Error reopening squawk', 'danger');
            }
        },

        formatDate(dateString) { return formatDate(dateString); },

        getPriorityClass(squawk) {
            return getSquawkPriorityClass(squawk.priority);
        }
    };
}
