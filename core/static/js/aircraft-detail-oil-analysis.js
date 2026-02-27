/**
 * Oil Analysis mixin for the aircraft detail page.
 * Provides state and methods for viewing, creating, editing, deleting
 * oil analysis reports, and AI-assisted PDF extraction.
 */

// 10-color palette for element trend lines
const OIL_ANALYSIS_PALETTE = [
    '#0066cc', '#c9190b', '#3e8635', '#f0ab00', '#8481dd',
    '#06c',    '#40199a', '#004368', '#8f4700', '#1d6060',
];

// Default elements shown on the chart (lead excluded — high values blow out the scale)
const OIL_ANALYSIS_DEFAULT_ELEMENTS = ['iron', 'copper', 'chromium', 'aluminum', 'silicon'];

// Periodic table symbols for each tracked element
const OIL_ANALYSIS_ELEMENT_SYMBOLS = {
    iron: 'Fe', copper: 'Cu', chromium: 'Cr', aluminum: 'Al', lead: 'Pb',
    silicon: 'Si', nickel: 'Ni', tin: 'Sn', molybdenum: 'Mo', magnesium: 'Mg',
    potassium: 'K', boron: 'B', sodium: 'Na', calcium: 'Ca', phosphorus: 'P',
    zinc: 'Zn', barium: 'Ba', silver: 'Ag', titanium: 'Ti', manganese: 'Mn',
};

// All tracked elements (lowercase, matches model constraint)
const OIL_ANALYSIS_ALL_ELEMENTS = [
    'iron', 'copper', 'chromium', 'aluminum', 'lead', 'silicon',
    'nickel', 'tin', 'molybdenum', 'magnesium', 'potassium', 'boron',
    'sodium', 'calcium', 'phosphorus', 'zinc', 'barium', 'silver',
    'titanium', 'manganese',
];

function oilAnalysisMixin() {
    return {
        // ---- State ---------------------------------------------------------
        oilAnalysisReports: [],
        oilAnalysisLoaded: false,
        oilAnalysisChart: null,
        oilAnalysisEngineComponents: [],
        oilAnalysisFilterComponent: null,

        // Element toggles — Set of element names to chart
        oilAnalysisSelectedElements: new Set(OIL_ANALYSIS_DEFAULT_ELEMENTS),

        // Visibility — Set of report IDs hidden from the chart (client-side only)
        oilAnalysisHiddenIds: new Set(),

        // CRUD modal
        oilAnalysisModalOpen: false,
        oilAnalysisSubmitting: false,
        editingOilAnalysisReport: null,
        oilAnalysisForm: _oilAnalysisEmptyForm(),

        // AI extract modal
        oilAnalysisAiModalOpen: false,
        oilAnalysisAiExtracting: false,
        oilAnalysisAiResults: null,
        oilAnalysisAiSampleIncludes: [],   // parallel array: true/false per sample
        oilAnalysisAiSampleComponents: [], // parallel array: component id per sample
        oilAnalysisAiJobId: null,
        oilAnalysisAiPollTimer: null,

        // ---- Computed getters ----------------------------------------------
        get oilAnalysisFilteredReports() {
            if (!this.oilAnalysisFilterComponent) return this.oilAnalysisReports;
            return this.oilAnalysisReports.filter(
                r => r.component && String(r.component) === String(this.oilAnalysisFilterComponent)
            );
        },

        // ---- Load -----------------------------------------------------------
        async loadOilAnalysis() {
            try {
                const params = this.oilAnalysisFilterComponent
                    ? `?component=${this.oilAnalysisFilterComponent}`
                    : '';
                const resp = await fetch(`/api/aircraft/${this.aircraftId}/oil_analysis/${params}`);
                const data = await resp.json();
                this.oilAnalysisReports = data.oil_analysis_reports || [];
                this.oilAnalysisEngineComponents = data.components || [];
                this.oilAnalysisLoaded = true;
                this.$nextTick(() => this.renderOilAnalysisChart());
            } catch (err) {
                console.error('Error loading oil analysis reports:', err);
                showNotification('Failed to load oil analysis reports', 'danger');
            }
        },

        // ---- CRUD modal ----------------------------------------------------
        openOilAnalysisModal() {
            this.editingOilAnalysisReport = null;
            this.oilAnalysisForm = {
                ..._oilAnalysisEmptyForm(),
                sample_date: new Date().toISOString().split('T')[0],
            };
            this.oilAnalysisModalOpen = true;
        },

        editOilAnalysisReport(report) {
            this.editingOilAnalysisReport = report;
            const elemPpm = Object.fromEntries(OIL_ANALYSIS_ALL_ELEMENTS.map(el => [el, '']));
            for (const [k, v] of Object.entries(report.elements_ppm || {})) {
                const key = k.toLowerCase();
                if (key in elemPpm && v != null) elemPpm[key] = v;
            }
            this.oilAnalysisForm = {
                component: report.component || '',
                sample_date: report.sample_date || '',
                analysis_date: report.analysis_date || '',
                lab: report.lab || '',
                lab_number: report.lab_number || '',
                oil_type: report.oil_type || '',
                oil_hours: report.oil_hours != null ? report.oil_hours : '',
                engine_hours: report.engine_hours != null ? report.engine_hours : '',
                oil_added_quarts: report.oil_added_quarts != null ? report.oil_added_quarts : '',
                elements_ppm: elemPpm,
                oil_properties: report.oil_properties ? JSON.stringify(report.oil_properties, null, 2) : '',
                lab_comments: report.lab_comments || '',
                status: report.status || '',
                notes: report.notes || '',
            };
            this.oilAnalysisModalOpen = true;
        },

        closeOilAnalysisModal() {
            this.oilAnalysisModalOpen = false;
            this.editingOilAnalysisReport = null;
        },

        async submitOilAnalysisReport() {
            if (this.oilAnalysisSubmitting) return;
            this.oilAnalysisSubmitting = true;
            try {
                const payload = _buildOilAnalysisPayload(this.oilAnalysisForm, this.aircraftId);

                let resp;
                if (this.editingOilAnalysisReport) {
                    resp = await apiRequest(
                        `/api/oil-analysis-reports/${this.editingOilAnalysisReport.id}/`,
                        { method: 'PATCH', body: JSON.stringify(payload) }
                    );
                } else {
                    resp = await apiRequest(
                        `/api/aircraft/${this.aircraftId}/oil_analysis/`,
                        { method: 'POST', body: JSON.stringify(payload) }
                    );
                }

                if (resp.ok) {
                    showNotification(
                        this.editingOilAnalysisReport ? 'Oil analysis report updated' : 'Oil analysis report added',
                        'success'
                    );
                    this.closeOilAnalysisModal();
                    this.oilAnalysisLoaded = false;
                    await this.loadOilAnalysis();
                } else {
                    showNotification(formatApiError(resp.data || {}, 'Failed to save oil analysis report'), 'danger');
                }
            } catch (err) {
                console.error('Error saving oil analysis report:', err);
                showNotification('Error saving oil analysis report', 'danger');
            } finally {
                this.oilAnalysisSubmitting = false;
            }
        },

        async deleteOilAnalysisReport() {
            if (!this.editingOilAnalysisReport || this.oilAnalysisSubmitting) return;
            this.oilAnalysisSubmitting = true;
            try {
                const resp = await apiRequest(
                    `/api/oil-analysis-reports/${this.editingOilAnalysisReport.id}/`,
                    { method: 'DELETE' }
                );
                if (resp.ok) {
                    showNotification('Oil analysis report deleted', 'success');
                    this.closeOilAnalysisModal();
                    this.oilAnalysisLoaded = false;
                    await this.loadOilAnalysis();
                } else {
                    showNotification('Failed to delete oil analysis report', 'danger');
                }
            } catch (err) {
                console.error('Error deleting oil analysis report:', err);
                showNotification('Error deleting oil analysis report', 'danger');
            } finally {
                this.oilAnalysisSubmitting = false;
            }
        },

        // ---- AI extract modal ----------------------------------------------
        openOilAnalysisAiModal() {
            this.oilAnalysisAiResults = null;
            this.oilAnalysisAiExtracting = false;
            this.oilAnalysisAiSampleIncludes = [];
            this.oilAnalysisAiSampleComponents = [];
            this.oilAnalysisAiModalOpen = true;
        },

        closeOilAnalysisAiModal() {
            this._stopOilAnalysisPoll();
            this.oilAnalysisAiModalOpen = false;
            this.oilAnalysisAiResults = null;
            this.oilAnalysisAiJobId = null;
        },

        _stopOilAnalysisPoll() {
            if (this.oilAnalysisAiPollTimer !== null) {
                clearInterval(this.oilAnalysisAiPollTimer);
                this.oilAnalysisAiPollTimer = null;
            }
        },

        async submitOilAnalysisAiFile() {
            const fileInput = document.getElementById('oilAnalysisAiFileInput');
            if (!fileInput || !fileInput.files.length) {
                showNotification('Please select a PDF file', 'warning');
                return;
            }
            this.oilAnalysisAiExtracting = true;
            this.oilAnalysisAiJobId = null;

            try {
                const formData = new FormData();
                formData.append('file', fileInput.files[0]);

                const resp = await fetch(
                    `/api/aircraft/${this.aircraftId}/oil_analysis_ai_extract/`,
                    {
                        method: 'POST',
                        headers: { 'X-CSRFToken': getCookie('csrftoken') },
                        body: formData,
                    }
                );

                if (resp.status === 202) {
                    const data = await resp.json();
                    this.oilAnalysisAiJobId = data.job_id;
                    this._startOilAnalysisPoll();
                } else {
                    const err = await resp.json().catch(() => ({}));
                    showNotification(formatApiError(err, 'Extraction failed'), 'danger');
                    this.oilAnalysisAiExtracting = false;
                }
            } catch (err) {
                console.error('Oil analysis AI extraction error:', err);
                showNotification('Extraction failed', 'danger');
                this.oilAnalysisAiExtracting = false;
            }
        },

        _startOilAnalysisPoll() {
            let cursor = 0;
            this.oilAnalysisAiPollTimer = setInterval(async () => {
                try {
                    const resp = await fetch(
                        `/api/aircraft/import/${this.oilAnalysisAiJobId}/?after=${cursor}`
                    );
                    if (!resp.ok) {
                        this._stopOilAnalysisPoll();
                        showNotification('Extraction failed: could not poll job status', 'danger');
                        this.oilAnalysisAiExtracting = false;
                        return;
                    }
                    const data = await resp.json();
                    cursor += (data.events || []).length;

                    if (data.status === 'completed') {
                        this._stopOilAnalysisPoll();
                        this.oilAnalysisAiExtracting = false;
                        const result = data.result || {};
                        this.oilAnalysisAiResults = result;
                        const samples = result.samples || [];
                        this.oilAnalysisAiSampleIncludes = samples.map(() => true);
                        // Pre-select first engine component if only one
                        const defaultComp = this.oilAnalysisEngineComponents.length === 1
                            ? this.oilAnalysisEngineComponents[0].id
                            : '';
                        this.oilAnalysisAiSampleComponents = samples.map(() => defaultComp);
                    } else if (data.status === 'failed') {
                        this._stopOilAnalysisPoll();
                        this.oilAnalysisAiExtracting = false;
                        const errorEvent = (data.events || []).findLast(e => e.type === 'error');
                        const msg = errorEvent ? errorEvent.message : 'Extraction failed';
                        showNotification(msg, 'danger');
                    }
                } catch (err) {
                    console.error('Oil analysis poll error:', err);
                    // Keep polling — transient network errors should not abort
                }
            }, 2000);
        },

        async saveOilAnalysisAiResults() {
            if (!this.oilAnalysisAiResults) return;
            const samples = this.oilAnalysisAiResults.samples || [];
            const topLevel = this.oilAnalysisAiResults;

            let saved = 0;
            let failed = 0;

            for (let i = 0; i < samples.length; i++) {
                if (!this.oilAnalysisAiSampleIncludes[i]) continue;

                const sample = samples[i];
                const payload = {
                    aircraft: this.aircraftId,
                    component: this.oilAnalysisAiSampleComponents[i] || null,
                    sample_date: sample.sample_date,
                    analysis_date: sample.analysis_date || null,
                    lab: topLevel.lab || '',
                    lab_number: topLevel.lab_number || '',
                    oil_type: topLevel.oil_type || '',
                    oil_hours: sample.oil_hours != null ? sample.oil_hours : null,
                    engine_hours: sample.engine_hours != null ? sample.engine_hours : null,
                    oil_added_quarts: sample.oil_added_quarts != null ? sample.oil_added_quarts : null,
                    elements_ppm: _stripNullElements(sample.elements_ppm || {}),
                    oil_properties: sample.oil_properties || null,
                    lab_comments: sample.lab_comments || '',
                    status: sample.status || null,
                    notes: '',
                };

                try {
                    const resp = await apiRequest(
                        `/api/aircraft/${this.aircraftId}/oil_analysis/`,
                        { method: 'POST', body: JSON.stringify(payload) }
                    );
                    if (resp.ok) {
                        saved++;
                    } else {
                        failed++;
                        console.error('Failed to save sample', i, resp.data);
                    }
                } catch (err) {
                    failed++;
                    console.error('Error saving sample', i, err);
                }
            }

            if (saved > 0) {
                showNotification(`${saved} oil analysis report${saved !== 1 ? 's' : ''} saved`, 'success');
                this.closeOilAnalysisAiModal();
                this.oilAnalysisLoaded = false;
                await this.loadOilAnalysis();
            }
            if (failed > 0) {
                showNotification(`${failed} report${failed !== 1 ? 's' : ''} failed to save`, 'danger');
            }
        },

        // ---- Element toggle ------------------------------------------------
        toggleOilAnalysisElement(name) {
            if (this.oilAnalysisSelectedElements.has(name)) {
                this.oilAnalysisSelectedElements.delete(name);
            } else {
                this.oilAnalysisSelectedElements.add(name);
            }
            // Trigger Alpine reactivity for Sets
            this.oilAnalysisSelectedElements = new Set(this.oilAnalysisSelectedElements);
            this.$nextTick(() => this.renderOilAnalysisChart());
        },

        elementSymbol(name) {
            return OIL_ANALYSIS_ELEMENT_SYMBOLS[name] || name;
        },

        isOilAnalysisElementSelected(name) {
            return this.oilAnalysisSelectedElements.has(name);
        },

        // ---- Chart ---------------------------------------------------------
        renderOilAnalysisChart() {
            const reports = [...this.oilAnalysisFilteredReports]
                .filter(r => r.sample_date && !this.oilAnalysisHiddenIds.has(r.id))
                .sort((a, b) => a.sample_date.localeCompare(b.sample_date));

            const canvas = document.getElementById('oilAnalysisChart');
            if (!canvas) return;

            if (this.oilAnalysisChart) {
                this.oilAnalysisChart.destroy();
                this.oilAnalysisChart = null;
            }

            if (reports.length < 2) return;

            const labels = reports.map(r => formatDate(r.sample_date));
            const elements = [...this.oilAnalysisSelectedElements];
            let paletteIdx = 0;

            const datasets = [];

            for (const element of elements) {
                const color = OIL_ANALYSIS_PALETTE[paletteIdx % OIL_ANALYSIS_PALETTE.length];
                paletteIdx++;

                const rawValues = reports.map(r => {
                    const v = r.elements_ppm?.[element];
                    return v != null ? parseFloat(v) : null;
                });

                // IQR outlier detection on non-null values
                const nonNull = rawValues.filter(v => v !== null);
                const bounds = computeOutlierBounds(nonNull);

                const pointColors = rawValues.map((v, i) => {
                    if (v === null) return color;
                    if (bounds && (v < bounds.lower || v > bounds.upper)) return '#f0ab00';
                    if (reports[i].excluded_from_averages) return '#8a8d90';
                    return color;
                });
                const pointRadii = rawValues.map((v, i) => {
                    if (v === null) return 0;
                    if (bounds && (v < bounds.lower || v > bounds.upper)) return 6;
                    if (reports[i].excluded_from_averages) return 5;
                    return 3;
                });

                // Per-element average (non-null, non-outlier, non-excluded)
                const avgVals = rawValues.filter((v, i) => {
                    if (v === null) return false;
                    if (reports[i].excluded_from_averages) return false;
                    if (!bounds) return true;
                    return v >= bounds.lower && v <= bounds.upper;
                });
                const avg = avgVals.length > 0
                    ? (avgVals.reduce((s, v) => s + v, 0) / avgVals.length).toFixed(1)
                    : null;

                datasets.push({
                    label: element.charAt(0).toUpperCase() + element.slice(1),
                    data: rawValues,
                    borderColor: color,
                    backgroundColor: 'transparent',
                    tension: 0.2,
                    pointBackgroundColor: pointColors,
                    pointBorderColor: pointColors,
                    pointRadius: pointRadii,
                    pointHoverRadius: pointRadii.map(r => r + 2),
                    spanGaps: true,
                });

                if (avg !== null) {
                    datasets.push({
                        label: `${element.charAt(0).toUpperCase() + element.slice(1)} avg (${avg})`,
                        data: new Array(reports.length).fill(parseFloat(avg)),
                        borderColor: color,
                        borderDash: [5, 4],
                        borderWidth: 1.5,
                        pointRadius: 0,
                        fill: false,
                        spanGaps: true,
                    });
                }
            }

            if (datasets.length === 0) return;

            const isMobile = window.innerWidth < 768;
            this.oilAnalysisChart = new Chart(canvas, {
                type: 'line',
                data: { labels, datasets },
                options: {
                    responsive: true,
                    scales: {
                        x: { title: { display: true, text: 'Sample Date' } },
                        y: { title: { display: true, text: 'PPM' }, beginAtZero: true },
                    },
                    plugins: {
                        legend: { display: !isMobile, position: 'bottom' },
                    },
                },
            });
        },

        /**
         * Delete a report directly from the grid without opening the modal.
         * Sets editingOilAnalysisReport and delegates to deleteOilAnalysisReport.
         */
        cardDeleteOilAnalysisReport(report) {
            this.editingOilAnalysisReport = report;
            this.deleteOilAnalysisReport();
        },

        /**
         * Toggle a report's visibility on the chart (client-side only, not persisted).
         */
        toggleOilAnalysisChartVisibility(report) {
            if (this.oilAnalysisHiddenIds.has(report.id)) {
                this.oilAnalysisHiddenIds.delete(report.id);
            } else {
                this.oilAnalysisHiddenIds.add(report.id);
            }
            // Trigger Alpine reactivity for Sets
            this.oilAnalysisHiddenIds = new Set(this.oilAnalysisHiddenIds);
            this.$nextTick(() => this.renderOilAnalysisChart());
        },

        /**
         * Toggle excluded_from_averages on a report in-place via PATCH.
         */
        async toggleOilAnalysisExcludeFromAverages(report) {
            const newVal = !report.excluded_from_averages;
            try {
                const resp = await apiRequest(
                    `/api/oil-analysis-reports/${report.id}/`,
                    { method: 'PATCH', body: JSON.stringify({ excluded_from_averages: newVal }) }
                );
                if (resp.ok) {
                    report.excluded_from_averages = newVal;
                    this.$nextTick(() => this.renderOilAnalysisChart());
                } else {
                    showNotification('Failed to update oil analysis report', 'danger');
                }
            } catch (err) {
                console.error('Error toggling oil analysis exclude:', err);
                showNotification('Error updating oil analysis report', 'danger');
            }
        },

        // ---- Status helpers ------------------------------------------------
        oilAnalysisStatusClass(status) {
            if (status === 'action_required') return 'pf-m-red';
            if (status === 'monitor') return 'pf-m-orange';
            if (status === 'normal') return 'pf-m-green';
            return '';
        },

        oilAnalysisStatusLabel(status) {
            if (status === 'action_required') return 'Action Required';
            if (status === 'monitor') return 'Monitor';
            if (status === 'normal') return 'Normal';
            return 'Unknown';
        },
    };
}

// ---- Private helpers (module-level, not on the mixin object) ---------------

function _oilAnalysisEmptyForm() {
    return {
        component: '',
        sample_date: '',
        analysis_date: '',
        lab: '',
        lab_number: '',
        oil_type: '',
        oil_hours: '',
        engine_hours: '',
        oil_added_quarts: '',
        elements_ppm: Object.fromEntries(OIL_ANALYSIS_ALL_ELEMENTS.map(el => [el, ''])),
        oil_properties: '',
        lab_comments: '',
        status: '',
        notes: '',
    };
}

function _buildOilAnalysisPayload(form, aircraftId) {
    const payload = {
        aircraft: aircraftId,
        sample_date: form.sample_date,
    };
    if (form.component) payload.component = form.component;
    if (form.analysis_date) payload.analysis_date = form.analysis_date;
    if (form.lab) payload.lab = form.lab;
    if (form.lab_number) payload.lab_number = form.lab_number;
    if (form.oil_type) payload.oil_type = form.oil_type;
    if (form.oil_hours !== '') payload.oil_hours = form.oil_hours;
    if (form.engine_hours !== '') payload.engine_hours = form.engine_hours;
    if (form.oil_added_quarts !== '') payload.oil_added_quarts = form.oil_added_quarts;
    if (form.lab_comments) payload.lab_comments = form.lab_comments;
    if (form.status) payload.status = form.status;
    if (form.notes) payload.notes = form.notes;

    const elements = {};
    for (const [k, v] of Object.entries(form.elements_ppm || {})) {
        if (v !== '' && v !== null && v !== undefined) {
            const n = parseFloat(v);
            if (!isNaN(n)) elements[k] = n;
        }
    }
    payload.elements_ppm = elements;
    try {
        payload.oil_properties = form.oil_properties ? JSON.parse(form.oil_properties) : null;
    } catch (e) {
        payload.oil_properties = null;
    }
    return payload;
}

function _stripNullElements(elementsObj) {
    const result = {};
    for (const [k, v] of Object.entries(elementsObj)) {
        if (v !== null && v !== undefined) result[k.toLowerCase()] = v;
    }
    return result;
}
