function eventsMixin() {
    return {
        // Recent events state (overview card)
        recentEvents: [],
        eventsLoaded: false,

        // History modal state
        eventsHistoryOpen: false,
        eventsHistoryAll: [],
        eventsHistoryCategory: '',
        eventsHistoryTotal: 0,
        eventsHistoryLoading: false,

        async loadRecentEvents() {
            try {
                const { ok, data } = await apiRequest(
                    `/api/aircraft/${this.aircraftId}/events/?limit=10`
                );
                if (ok) {
                    this.recentEvents = data.events;
                }
            } catch (error) {
                console.error('Error loading recent events:', error);
            } finally {
                this.eventsLoaded = true;
            }
        },

        openEventsHistory() {
            this.eventsHistoryOpen = true;
            this.eventsHistoryCategory = '';
            this.loadEventsHistory();
        },

        closeEventsHistory() {
            this.eventsHistoryOpen = false;
            this.eventsHistoryAll = [];
        },

        async loadEventsHistory() {
            this.eventsHistoryLoading = true;
            try {
                let url = `/api/aircraft/${this.aircraftId}/events/?limit=200`;
                if (this.eventsHistoryCategory) {
                    url += `&category=${encodeURIComponent(this.eventsHistoryCategory)}`;
                }
                const { ok, data } = await apiRequest(url);
                if (ok) {
                    this.eventsHistoryAll = data.events;
                    this.eventsHistoryTotal = data.total;
                }
            } catch (error) {
                console.error('Error loading events history:', error);
            } finally {
                this.eventsHistoryLoading = false;
            }
        },

        eventCategoryLabel(cat) {
            const labels = {
                hours: 'Hours',
                component: 'Component',
                squawk: 'Squawk',
                note: 'Note',
                oil: 'Oil',
                fuel: 'Fuel',
                logbook: 'Logbook',
                ad: 'AD',
                inspection: 'Inspection',
                document: 'Document',
                aircraft: 'Aircraft',
            };
            return labels[cat] || cat;
        },

        eventCategoryClass(cat) {
            const classes = {
                hours: 'pf-m-blue',
                component: 'pf-m-purple',
                squawk: 'pf-m-orange',
                note: 'pf-m-cyan',
                oil: 'pf-m-gold',
                fuel: 'pf-m-green',
                logbook: 'pf-m-blue',
                ad: 'pf-m-red',
                inspection: 'pf-m-purple',
                document: 'pf-m-cyan',
                aircraft: 'pf-m-blue',
            };
            return classes[cat] || '';
        },

        formatEventTime(ts) {
            if (!ts) return '';
            const d = new Date(ts);
            const now = new Date();
            const diffMs = now - d;
            const diffMins = Math.floor(diffMs / 60000);
            const diffHrs = Math.floor(diffMs / 3600000);
            const diffDays = Math.floor(diffMs / 86400000);

            if (diffMins < 1) return 'Just now';
            if (diffMins < 60) return `${diffMins}m ago`;
            if (diffHrs < 24) return `${diffHrs}h ago`;
            if (diffDays < 7) return `${diffDays}d ago`;
            return d.toLocaleDateString();
        },
    };
}
