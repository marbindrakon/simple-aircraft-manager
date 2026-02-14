function fuelMixin() {
    return {
        // Fuel tracking state
        fuelRecords: [],
        fuelLoaded: false,
        fuelModalOpen: false,
        fuelSubmitting: false,
        fuelChart: null,
        fuelForm: {
            date: '',
            quantity_added: '',
            level_after: '',
            fuel_type: '',
            flight_hours: '',
            notes: '',
        },

        async loadFuelRecords() {
            try {
                const response = await fetch(`/api/aircraft/${this.aircraftId}/fuel_records/`);
                const data = await response.json();
                this.fuelRecords = data.fuel_records || [];
                this.fuelLoaded = true;
                this.$nextTick(() => this.renderFuelChart());
            } catch (error) {
                console.error('Error loading fuel records:', error);
                showNotification('Failed to load fuel records', 'danger');
            }
        },

        openFuelModal() {
            this.fuelForm = {
                date: new Date().toISOString().split('T')[0],
                quantity_added: '',
                level_after: '',
                fuel_type: '',
                flight_hours: '',
                notes: '',
            };
            this.fuelModalOpen = true;
        },

        closeFuelModal() {
            this.fuelModalOpen = false;
        },

        async submitFuelRecord() {
            if (this.fuelSubmitting) return;
            this.fuelSubmitting = true;
            try {
                const data = {
                    date: this.fuelForm.date,
                    quantity_added: this.fuelForm.quantity_added,
                };
                if (this.fuelForm.level_after) data.level_after = this.fuelForm.level_after;
                if (this.fuelForm.fuel_type) data.fuel_type = this.fuelForm.fuel_type;
                if (this.fuelForm.flight_hours) data.flight_hours = this.fuelForm.flight_hours;
                if (this.fuelForm.notes) data.notes = this.fuelForm.notes;

                const response = await fetch(`/api/aircraft/${this.aircraftId}/fuel_records/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                    body: JSON.stringify(data),
                });

                if (response.ok) {
                    showNotification('Fuel record added', 'success');
                    this.closeFuelModal();
                    this.fuelLoaded = false;
                    await this.loadFuelRecords();
                } else {
                    const errorData = await response.json();
                    showNotification(JSON.stringify(errorData) || 'Failed to add fuel record', 'danger');
                }
            } catch (error) {
                console.error('Error adding fuel record:', error);
                showNotification('Error adding fuel record', 'danger');
            } finally {
                this.fuelSubmitting = false;
            }
        },

        renderFuelChart() {
            if (this.fuelRecords.length < 2) return;
            const canvas = document.getElementById('fuelChart');
            if (!canvas) return;

            if (this.fuelChart) {
                this.fuelChart.destroy();
            }

            const sorted = [...this.fuelRecords].sort((a, b) => parseFloat(a.flight_hours) - parseFloat(b.flight_hours));

            const labels = [];
            const dataPoints = [];
            for (let i = 1; i < sorted.length; i++) {
                const hoursDelta = parseFloat(sorted[i].flight_hours) - parseFloat(sorted[i - 1].flight_hours);
                const qty = parseFloat(sorted[i].quantity_added);
                if (qty > 0 && hoursDelta > 0) {
                    labels.push(parseFloat(sorted[i].flight_hours).toFixed(1));
                    dataPoints.push((qty / hoursDelta).toFixed(1));
                }
            }

            if (dataPoints.length === 0) return;

            const fuelAvg = (dataPoints.reduce((sum, v) => sum + parseFloat(v), 0) / dataPoints.length).toFixed(1);
            const fuelAvgLine = new Array(dataPoints.length).fill(fuelAvg);

            this.fuelChart = new Chart(canvas, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Gallons per Hour',
                        data: dataPoints,
                        borderColor: '#009596',
                        backgroundColor: 'rgba(0, 149, 150, 0.1)',
                        fill: true,
                        tension: 0.3,
                    }, {
                        label: `Average (${fuelAvg})`,
                        data: fuelAvgLine,
                        borderColor: '#009596',
                        borderDash: [6, 4],
                        borderWidth: 2,
                        pointRadius: 0,
                        fill: false,
                    }],
                },
                options: {
                    responsive: true,
                    scales: {
                        x: { title: { display: true, text: 'Aircraft Hours' } },
                        y: { title: { display: true, text: 'Gallons per Hour' }, beginAtZero: true },
                    },
                },
            });
        },
    };
}
