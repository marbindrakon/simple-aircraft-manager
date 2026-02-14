function hoursUpdateModal() {
    return {
        isOpen: false,
        aircraft: null,
        currentHours: 0,
        newHours: 0,
        submitting: false,
        errorMessage: '',

        get hoursAdded() {
            const delta = this.newHours - this.currentHours;
            return delta > 0 ? delta.toFixed(1) : 0;
        },

        get canSubmit() {
            return this.newHours >= this.currentHours && !this.submitting;
        },

        open(aircraft) {
            this.aircraft = aircraft;
            this.currentHours = parseFloat(aircraft.flight_time) || 0;
            this.newHours = this.currentHours;
            this.errorMessage = '';
            this.isOpen = true;
        },

        close() {
            this.isOpen = false;
            this.reset();
        },

        reset() {
            setTimeout(() => {
                this.aircraft = null;
                this.currentHours = 0;
                this.newHours = 0;
                this.submitting = false;
                this.errorMessage = '';
            }, 300);
        },

        async submit() {
            if (this.submitting || !this.canSubmit) return;

            this.submitting = true;
            this.errorMessage = '';

            try {
                const { ok, data } = await apiRequest(
                    `/api/aircraft/${this.aircraft.id}/update_hours/`,
                    {
                        method: 'POST',
                        body: JSON.stringify({ new_hours: this.newHours }),
                    }
                );

                if (ok && data.success) {
                    showNotification(
                        `Hours updated to ${data.aircraft_hours} (+${data.hours_added} hours, ${data.components_updated} components updated)`,
                        'success'
                    );
                    window.dispatchEvent(new CustomEvent('aircraft-updated'));
                    this.close();
                } else {
                    this.errorMessage = data?.error || 'Update failed';
                }
            } catch (error) {
                console.error('Error updating hours:', error);
                this.errorMessage = 'Network error occurred';
            } finally {
                this.submitting = false;
            }
        }
    }
}
