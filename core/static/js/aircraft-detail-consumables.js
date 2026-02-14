/**
 * Factory that creates oil and fuel record mixins. Both share identical
 * logic; only units, chart calculations, and display labels differ.
 *
 * @param {Object} cfg
 * @param {string} cfg.prefix          - State prefix: 'oil' or 'fuel'
 * @param {string} cfg.endpoint        - API action name: 'oil_records' or 'fuel_records'
 * @param {string} cfg.responseKey     - JSON key in GET response: 'oil_records' or 'fuel_records'
 * @param {string} cfg.chartCanvasId   - Canvas element id: 'oilChart' or 'fuelChart'
 * @param {function} cfg.chartMetric   - (hoursDelta, qty) => datapoint value
 * @param {string} cfg.chartLabel      - Y-axis and dataset label
 * @param {string} cfg.chartColor      - Primary colour hex
 * @param {string} cfg.chartColorBg    - Fill colour rgba string
 * @param {string} cfg.addedMsg        - Success notification text on create
 * @param {string} cfg.updatedMsg      - Success notification text on update
 */
function makeConsumableMixin(cfg) {
    const {
        prefix,
        endpoint,
        responseKey,
        chartCanvasId,
        chartMetric,
        chartLabel,
        chartColor,
        chartColorBg,
        addedMsg,
        updatedMsg,
    } = cfg;

    // Derive capitalised prefix once (e.g. 'Oil', 'Fuel')
    const Cap = prefix.charAt(0).toUpperCase() + prefix.slice(1);

    const records       = `${prefix}Records`;
    const loaded        = `${prefix}Loaded`;
    const modalOpen     = `${prefix}ModalOpen`;
    const submitting    = `${prefix}Submitting`;
    const chart         = `${prefix}Chart`;
    const form          = `${prefix}Form`;
    const editingRecord = `editing${Cap}Record`;

    const emptyForm = () => ({
        date: '',
        quantity_added: '',
        level_after: '',
        consumable_type: '',
        flight_hours: '',
        notes: '',
    });

    return {
        [records]:       [],
        [loaded]:        false,
        [modalOpen]:     false,
        [submitting]:    false,
        [chart]:         null,
        [form]:          emptyForm(),
        [editingRecord]: null,

        async [`load${Cap}Records`]() {
            try {
                const response = await fetch(`/api/aircraft/${this.aircraftId}/${endpoint}/`);
                const data = await response.json();
                this[records] = data[responseKey] || [];
                this[loaded] = true;
                this.$nextTick(() => this[`render${Cap}Chart`]());
            } catch (error) {
                console.error(`Error loading ${prefix} records:`, error);
                showNotification(`Failed to load ${prefix} records`, 'danger');
            }
        },

        [`open${Cap}Modal`]() {
            this[editingRecord] = null;
            this[form] = { ...emptyForm(), date: new Date().toISOString().split('T')[0] };
            this[modalOpen] = true;
        },

        [`edit${Cap}Record`](record) {
            this[editingRecord] = record;
            this[form] = {
                date: record.date,
                quantity_added: record.quantity_added,
                level_after: record.level_after || '',
                consumable_type: record.consumable_type || '',
                flight_hours: record.flight_hours,
                notes: record.notes || '',
            };
            this[modalOpen] = true;
        },

        [`close${Cap}Modal`]() {
            this[modalOpen] = false;
            this[editingRecord] = null;
        },

        async [`submit${Cap}Record`]() {
            if (this[submitting]) return;
            this[submitting] = true;
            try {
                const payload = {
                    date: this[form].date,
                    quantity_added: this[form].quantity_added,
                };
                if (this[form].level_after) payload.level_after = this[form].level_after;
                if (this[form].consumable_type) payload.consumable_type = this[form].consumable_type;
                if (this[form].flight_hours) payload.flight_hours = this[form].flight_hours;
                if (this[form].notes) payload.notes = this[form].notes;

                let response;
                if (this[editingRecord]) {
                    response = await fetch(`/api/consumable-records/${this[editingRecord].id}/`, {
                        method: 'PATCH',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': getCookie('csrftoken'),
                        },
                        body: JSON.stringify(payload),
                    });
                } else {
                    response = await fetch(`/api/aircraft/${this.aircraftId}/${endpoint}/`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': getCookie('csrftoken'),
                        },
                        body: JSON.stringify(payload),
                    });
                }

                if (response.ok) {
                    showNotification(this[editingRecord] ? updatedMsg : addedMsg, 'success');
                    this[`close${Cap}Modal`]();
                    this[loaded] = false;
                    await this[`load${Cap}Records`]();
                } else {
                    const errorData = await response.json();
                    showNotification(formatApiError(errorData, `Failed to save ${prefix} record`), 'danger');
                }
            } catch (error) {
                console.error(`Error saving ${prefix} record:`, error);
                showNotification(`Error saving ${prefix} record`, 'danger');
            } finally {
                this[submitting] = false;
            }
        },

        async [`delete${Cap}Record`]() {
            if (!this[editingRecord] || this[submitting]) return;
            this[submitting] = true;
            try {
                const response = await fetch(`/api/consumable-records/${this[editingRecord].id}/`, {
                    method: 'DELETE',
                    headers: { 'X-CSRFToken': getCookie('csrftoken') },
                });

                if (response.ok) {
                    showNotification(`${Cap} record deleted`, 'success');
                    this[`close${Cap}Modal`]();
                    this[loaded] = false;
                    await this[`load${Cap}Records`]();
                } else {
                    showNotification(`Failed to delete ${prefix} record`, 'danger');
                }
            } catch (error) {
                console.error(`Error deleting ${prefix} record:`, error);
                showNotification(`Error deleting ${prefix} record`, 'danger');
            } finally {
                this[submitting] = false;
            }
        },

        [`render${Cap}Chart`]() {
            if (this[records].length < 2) return;
            const canvas = document.getElementById(chartCanvasId);
            if (!canvas) return;

            if (this[chart]) {
                this[chart].destroy();
            }

            const sorted = [...this[records]].sort(
                (a, b) => parseFloat(a.flight_hours) - parseFloat(b.flight_hours)
            );

            const labels = [];
            const dataPoints = [];
            for (let i = 1; i < sorted.length; i++) {
                const hoursDelta = parseFloat(sorted[i].flight_hours) - parseFloat(sorted[i - 1].flight_hours);
                const qty = parseFloat(sorted[i].quantity_added);
                if (qty > 0 && hoursDelta > 0) {
                    labels.push(parseFloat(sorted[i].flight_hours).toFixed(1));
                    dataPoints.push(chartMetric(hoursDelta, qty));
                }
            }

            if (dataPoints.length === 0) return;

            const avg = (dataPoints.reduce((sum, v) => sum + parseFloat(v), 0) / dataPoints.length).toFixed(1);

            this[chart] = new Chart(canvas, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: chartLabel,
                        data: dataPoints,
                        borderColor: chartColor,
                        backgroundColor: chartColorBg,
                        fill: true,
                        tension: 0.3,
                    }, {
                        label: `Average (${avg})`,
                        data: new Array(dataPoints.length).fill(avg),
                        borderColor: chartColor,
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
                        y: { title: { display: true, text: chartLabel }, beginAtZero: true },
                    },
                },
            });
        },
    };
}
