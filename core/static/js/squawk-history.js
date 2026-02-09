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
                // Load aircraft info and resolved squawks in parallel
                const [aircraftRes, squawksRes] = await Promise.all([
                    fetch(`/api/aircraft/${this.aircraftId}/`),
                    fetch(`/api/aircraft/${this.aircraftId}/squawks/?resolved=true`)
                ]);

                if (aircraftRes.ok) {
                    this.aircraft = await aircraftRes.json();
                }

                if (squawksRes.ok) {
                    const data = await squawksRes.json();
                    this.resolvedSquawks = data.squawks || [];
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
                const response = await fetch(`/api/squawks/${squawk.id}/`, {
                    method: 'PATCH',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                    body: JSON.stringify({ resolved: false }),
                });

                if (response.ok) {
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

        formatDate(dateString) {
            return new Date(dateString).toLocaleDateString();
        },

        getPriorityClass(squawk) {
            switch (squawk.priority) {
                case 0:
                    return 'pf-m-red';
                case 1:
                    return 'pf-m-orange';
                case 2:
                    return 'pf-m-blue';
                default:
                    return 'pf-m-grey';
            }
        }
    };
}
