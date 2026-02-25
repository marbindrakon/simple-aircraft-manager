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

/**
 * Compute IQR-based outlier bounds for an array of numeric values.
 * Returns null if there are fewer than 5 values or the IQR is zero
 * (meaning no discrimination is possible).
 *
 * @param {number[]} values
 * @returns {{ lower: number, upper: number } | null}
 */
function computeOutlierBounds(values) {
    if (values.length < 5) return null;
    const nums = [...values].map(v => parseFloat(v)).sort((a, b) => a - b);
    const n = nums.length;
    const q1 = nums[Math.floor(n / 4)];
    const q3 = nums[Math.floor((3 * n) / 4)];
    const iqr = q3 - q1;
    if (iqr === 0) return null;
    return { lower: q1 - 1.5 * iqr, upper: q3 + 1.5 * iqr };
}

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
    const outlierIds    = `${prefix}OutlierIds`;

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
        [outlierIds]:    new Set(),

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

        /**
         * Delete a record directly from the card without opening the modal.
         * Sets editingRecord and delegates to delete${Cap}Record.
         */
        [`cardDelete${Cap}Record`](record) {
            this[editingRecord] = record;
            this[`delete${Cap}Record`]();
        },

        /**
         * Returns true if the given record ID was flagged as an outlier
         * during the last chart render.
         */
        [`is${Cap}Outlier`](recordId) {
            return this[outlierIds].has(recordId);
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
            const pointIds = [];  // record ID for each datapoint (the "current" record in the pair)
            for (let i = 1; i < sorted.length; i++) {
                const hoursDelta = parseFloat(sorted[i].flight_hours) - parseFloat(sorted[i - 1].flight_hours);
                const qty = parseFloat(sorted[i].quantity_added);
                if (qty > 0 && hoursDelta > 0) {
                    labels.push(parseFloat(sorted[i].flight_hours).toFixed(1));
                    dataPoints.push(chartMetric(hoursDelta, qty));
                    pointIds.push(sorted[i].id);
                }
            }

            if (dataPoints.length === 0) return;

            // --- Outlier detection (IQR method, requires >= 5 datapoints) ---
            const OUTLIER_COLOR = '#f0ab00';  // PatternFly warning orange
            const bounds = computeOutlierBounds(dataPoints);
            const isOutlierPoint = dataPoints.map(v => {
                if (!bounds) return false;
                const n = parseFloat(v);
                return n < bounds.lower || n > bounds.upper;
            });

            // Propagate outlier record IDs to mixin state so the template can read them
            const newOutlierIds = new Set();
            isOutlierPoint.forEach((isOut, i) => { if (isOut) newOutlierIds.add(pointIds[i]); });
            this[outlierIds] = newOutlierIds;

            // --- Average: last 20 datapoints, outliers excluded ---
            const avgWindow      = dataPoints.slice(-20);
            const avgWindowFlags = isOutlierPoint.slice(-20);
            const avgValues      = avgWindow.filter((_, i) => !avgWindowFlags[i]);
            const excludedCount  = avgWindow.length - avgValues.length;
            // Fallback: if every point in the window is an outlier, include them all
            const avgSource = avgValues.length > 0 ? avgValues : avgWindow;
            const avg = (avgSource.reduce((sum, v) => sum + parseFloat(v), 0) / avgSource.length).toFixed(1);

            // --- Per-point chart styling ---
            const pointColors = isOutlierPoint.map(isOut => isOut ? OUTLIER_COLOR : chartColor);
            const pointRadii  = isOutlierPoint.map(isOut => isOut ? 6 : 3);

            const avgLabel = excludedCount > 0
                ? `Average (${avg}, ${excludedCount} outlier${excludedCount !== 1 ? 's' : ''} excluded)`
                : `Average (${avg})`;

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
                        pointBackgroundColor: pointColors,
                        pointBorderColor: pointColors,
                        pointRadius: pointRadii,
                        pointHoverRadius: pointRadii.map(r => r + 2),
                    }, {
                        label: avgLabel,
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
