function aircraftSwitcherMixin() {
    return {
        switcherAircraft: [],
        switcherOpen: false,
        switcherLoaded: false,

        async loadSwitcherAircraft() {
            try {
                const resp = await apiRequest('/api/aircraft/');
                if (resp.ok) {
                    const list = Array.isArray(resp.data) ? resp.data : (resp.data.results || []);
                    this.switcherAircraft = list.filter(a => a.id !== this.aircraftId);
                }
                this.switcherLoaded = true;
            } catch (error) {
                console.error('Error loading aircraft list:', error);
                this.switcherLoaded = true;
            }
        },

        toggleSwitcher() {
            this.switcherOpen = !this.switcherOpen;
            if (this.switcherOpen && !this.switcherLoaded) {
                this.loadSwitcherAircraft();
            }
        },

        navigateToAircraft(id) {
            window.location.href = '/aircraft/' + id + '/';
        },
    };
}
