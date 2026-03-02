function aircraftSwitcherMixin() {
    return {
        switcherAircraft: [],
        switcherOpen: false,

        async loadSwitcherAircraft() {
            try {
                const resp = await apiRequest('/api/aircraft/');
                if (resp.ok) {
                    const list = Array.isArray(resp.data) ? resp.data : (resp.data.results || []);
                    this.switcherAircraft = list.filter(a => a.id !== this.aircraftId);
                }
            } catch (error) {
                console.error('Error loading aircraft list:', error);
            }
        },

        toggleSwitcher() {
            this.switcherOpen = !this.switcherOpen;
        },

        navigateToAircraft(id) {
            window.location.href = '/aircraft/' + id + '/';
        },
    };
}
