function hoursUpdateModal() {
    return {
        isOpen: false,
        aircraft: null,
        currentTachTime: 0,
        newTachReading: 0,
        currentHobbsTime: 0,
        newHobbsReading: 0,
        submitting: false,
        errorMessage: '',

        get tachOffset() {
            return parseFloat(this.aircraft?.tach_time_offset) || 0;
        },

        get hobbsOffset() {
            return parseFloat(this.aircraft?.hobbs_time_offset) || 0;
        },

        get hoursAdded() {
            const cumulative = this.newTachReading + this.tachOffset;
            const delta = cumulative - this.currentTachTime;
            return delta > 0 ? delta.toFixed(1) : 0;
        },

        get canSubmit() {
            const cumulative = this.newTachReading + this.tachOffset;
            return cumulative >= this.currentTachTime && !this.submitting;
        },

        open(aircraft) {
            this.aircraft = aircraft;
            this.currentTachTime = parseFloat(aircraft.tach_time) || 0;
            // Pre-fill reading = cumulative - offset
            this.newTachReading = this.currentTachTime - this.tachOffset;
            this.currentHobbsTime = parseFloat(aircraft.hobbs_time) || 0;
            this.newHobbsReading = this.currentHobbsTime - this.hobbsOffset;
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
                this.currentTachTime = 0;
                this.newTachReading = 0;
                this.currentHobbsTime = 0;
                this.newHobbsReading = 0;
                this.submitting = false;
                this.errorMessage = '';
            }, 300);
        },

        async submit() {
            if (this.submitting || !this.canSubmit) return;

            this.submitting = true;
            this.errorMessage = '';

            const newTachCumulative = this.newTachReading + this.tachOffset;
            const newHobbsCumulative = this.newHobbsReading + this.hobbsOffset;
            const body = { new_tach_time: newTachCumulative };
            if (newHobbsCumulative > 0) {
                body.new_hobbs_time = newHobbsCumulative;
            }

            try {
                const { ok, data } = await apiRequest(
                    `/api/aircraft/${this.aircraft.id}/update_hours/`,
                    {
                        method: 'POST',
                        body: JSON.stringify(body),
                    }
                );

                if (ok && data.success) {
                    showNotification(
                        `Hours updated to ${data.tach_time} (+${data.hours_added} hours, ${data.components_updated} components updated)`,
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
