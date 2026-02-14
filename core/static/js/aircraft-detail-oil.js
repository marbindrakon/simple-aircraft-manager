function oilMixin() {
    return {
        // Oil tracking state
        oilRecords: [],
        oilLoaded: false,
        oilModalOpen: false,
        oilSubmitting: false,
        oilChart: null,
        oilForm: {
            date: '',
            quantity_added: '',
            level_after: '',
            oil_type: '',
            flight_hours: '',
            notes: '',
        },

        async loadOilRecords() {
            try {
                const response = await fetch(`/api/aircraft/${this.aircraftId}/oil_records/`);
                const data = await response.json();
                this.oilRecords = data.oil_records || [];
                this.oilLoaded = true;
                this.$nextTick(() => this.renderOilChart());
            } catch (error) {
                console.error('Error loading oil records:', error);
                showNotification('Failed to load oil records', 'danger');
            }
        },

        openOilModal() {
            this.oilForm = {
                date: new Date().toISOString().split('T')[0],
                quantity_added: '',
                level_after: '',
                oil_type: '',
                flight_hours: '',
                notes: '',
            };
            this.oilModalOpen = true;
        },

        closeOilModal() {
            this.oilModalOpen = false;
        },

        async submitOilRecord() {
            if (this.oilSubmitting) return;
            this.oilSubmitting = true;
            try {
                const data = {
                    date: this.oilForm.date,
                    quantity_added: this.oilForm.quantity_added,
                };
                if (this.oilForm.level_after) data.level_after = this.oilForm.level_after;
                if (this.oilForm.oil_type) data.oil_type = this.oilForm.oil_type;
                if (this.oilForm.flight_hours) data.flight_hours = this.oilForm.flight_hours;
                if (this.oilForm.notes) data.notes = this.oilForm.notes;

                const response = await fetch(`/api/aircraft/${this.aircraftId}/oil_records/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                    body: JSON.stringify(data),
                });

                if (response.ok) {
                    showNotification('Oil record added', 'success');
                    this.closeOilModal();
                    this.oilLoaded = false;
                    await this.loadOilRecords();
                } else {
                    const errorData = await response.json();
                    showNotification(JSON.stringify(errorData) || 'Failed to add oil record', 'danger');
                }
            } catch (error) {
                console.error('Error adding oil record:', error);
                showNotification('Error adding oil record', 'danger');
            } finally {
                this.oilSubmitting = false;
            }
        },

        renderOilChart() {
            if (this.oilRecords.length < 2) return;
            const canvas = document.getElementById('oilChart');
            if (!canvas) return;

            if (this.oilChart) {
                this.oilChart.destroy();
            }

            const sorted = [...this.oilRecords].sort((a, b) => parseFloat(a.flight_hours) - parseFloat(b.flight_hours));

            const labels = [];
            const dataPoints = [];
            for (let i = 1; i < sorted.length; i++) {
                const hoursDelta = parseFloat(sorted[i].flight_hours) - parseFloat(sorted[i - 1].flight_hours);
                const qty = parseFloat(sorted[i].quantity_added);
                if (qty > 0 && hoursDelta > 0) {
                    labels.push(parseFloat(sorted[i].flight_hours).toFixed(1));
                    dataPoints.push((hoursDelta / qty).toFixed(1));
                }
            }

            if (dataPoints.length === 0) return;

            const oilAvg = (dataPoints.reduce((sum, v) => sum + parseFloat(v), 0) / dataPoints.length).toFixed(1);
            const oilAvgLine = new Array(dataPoints.length).fill(oilAvg);

            this.oilChart = new Chart(canvas, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Hours per Quart',
                        data: dataPoints,
                        borderColor: '#0066cc',
                        backgroundColor: 'rgba(0, 102, 204, 0.1)',
                        fill: true,
                        tension: 0.3,
                    }, {
                        label: `Average (${oilAvg})`,
                        data: oilAvgLine,
                        borderColor: '#0066cc',
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
                        y: { title: { display: true, text: 'Hours per Quart' }, beginAtZero: true },
                    },
                },
            });
        },
    };
}
