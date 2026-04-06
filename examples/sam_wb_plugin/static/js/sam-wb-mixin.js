/**
 * Weight & Balance plugin — Alpine.js mixin.
 *
 * Pushed onto window.SAMPluginMixins so aircraft-detail.js merges it into
 * the aircraftDetail() Alpine component via mergeMixins().  All core
 * properties (aircraftId, isOwner, features, apiRequest, showNotification,
 * formatDate) are available on `this` after merging.
 *
 * Initialisation:
 *   The mixin is lazy-loaded when the user first switches to the "W&B" tab.
 *   The tab template uses x-effect to call initWb() on first activation.
 *
 * Data flow:
 *   1. initWb() → loadWbConfig() + loadWbCalculations() in parallel
 *   2. loadWbConfig() populates this.wbConfig and resets the live calculator
 *   3. Live calculator items (this.wbItems) are reactive — getters recompute
 *      gross weight and CG automatically as the user types weights
 *   4. saveWbCalculation() POSTs to /api/wb-calculations/ which computes and
 *      stores the totals server-side, then prepends the result to wbCalculations
 */

window.SAMPluginMixins = window.SAMPluginMixins || [];
window.SAMPluginMixins.push(function wbMixin() {
    return {

        // ----------------------------------------------------------------
        // State
        // ----------------------------------------------------------------

        wbConfig: null,           // WBConfig object from API, or null if not configured
        wbConfigLoaded: false,    // true once the config fetch completes (even if null)
        wbCalculations: [],       // saved WBCalculation objects
        wbCalcsLoaded: false,

        // Live calculator — parallel array to wbConfig.stations
        wbItems: [],              // [{station_name, arm, weight}]
        wbCalcLabel: '',
        wbCalcNotes: '',
        wbSaving: false,

        // Config editor modal
        wbConfigModalOpen: false,
        wbConfigSaving: false,
        wbConfigForm: {},         // editable copy while modal is open

        // Delete confirmation
        wbDeleteConfirmId: null,

        // ----------------------------------------------------------------
        // Initialisation (called by x-effect in detail_wb.html)
        // ----------------------------------------------------------------

        async initWb() {
            await Promise.all([this.loadWbConfig(), this.loadWbCalculations()]);
        },

        // ----------------------------------------------------------------
        // Config loading
        // ----------------------------------------------------------------

        async loadWbConfig() {
            const { ok, data } = await apiRequest(
                `/api/wb-configs/?aircraft=${this.aircraftId}`
            );
            if (ok) {
                // SAM has no DRF pagination — list endpoints return a flat array.
                const results = Array.isArray(data) ? data : (data.results || []);
                this.wbConfig = results.length > 0 ? results[0] : null;
                if (this.wbConfig) this._resetWbItems();
            }
            this.wbConfigLoaded = true;
        },

        /** Rebuild the live calculator items from the current config stations. */
        _resetWbItems() {
            const stations = (this.wbConfig && this.wbConfig.stations) || [];
            this.wbItems = stations.map(s => ({
                station_name: s.name,
                arm: parseFloat(s.arm),
                weight: 0,
            }));
        },

        // ----------------------------------------------------------------
        // Live calculator — reactive getters
        // ----------------------------------------------------------------

        /** Sum of all station weights entered in the calculator (payload only). */
        get wbPayloadWeight() {
            return this.wbItems.reduce(
                (sum, item) => sum + (parseFloat(item.weight) || 0), 0
            );
        },

        /** Sum of (weight × arm) for all stations (payload only). */
        get wbPayloadMoment() {
            return this.wbItems.reduce(
                (sum, item) => sum + (parseFloat(item.weight) || 0) * item.arm, 0
            );
        },

        /** Empty weight from config (0 if no config). */
        get wbEmptyWeight() {
            return this.wbConfig ? parseFloat(this.wbConfig.empty_weight) : 0;
        },

        /** Empty moment = empty_weight × empty_cg. */
        get wbEmptyMoment() {
            if (!this.wbConfig) return 0;
            return parseFloat(this.wbConfig.empty_weight) * parseFloat(this.wbConfig.empty_cg);
        },

        /** Gross weight = empty + payload. */
        get wbGrossWeight() {
            return this.wbEmptyWeight + this.wbPayloadWeight;
        },

        /** Gross moment = empty moment + payload moment. */
        get wbGrossMoment() {
            return this.wbEmptyMoment + this.wbPayloadMoment;
        },

        /** Gross CG = gross moment / gross weight. */
        get wbGrossCG() {
            return this.wbGrossWeight > 0
                ? this.wbGrossMoment / this.wbGrossWeight
                : 0;
        },

        /**
         * Whether the current loading is within the certified envelope.
         * Returns null when there is no config or no weight entered yet.
         */
        get wbWithinLimits() {
            if (!this.wbConfig || this.wbGrossWeight <= 0) return null;
            const cfg = this.wbConfig;
            return (
                this.wbGrossWeight <= parseFloat(cfg.max_gross_weight) &&
                this.wbGrossCG >= parseFloat(cfg.fwd_cg_limit) &&
                this.wbGrossCG <= parseFloat(cfg.aft_cg_limit)
            );
        },

        /** CSS class for the result banner (green / red / neutral). */
        get wbResultClass() {
            if (this.wbWithinLimits === null) return '';
            return this.wbWithinLimits ? 'pf-m-success' : 'pf-m-danger';
        },

        /** How many pounds remain before max gross weight. */
        get wbWeightMargin() {
            if (!this.wbConfig) return null;
            return parseFloat(this.wbConfig.max_gross_weight) - this.wbGrossWeight;
        },

        // ----------------------------------------------------------------
        // Save / load calculations
        // ----------------------------------------------------------------

        async saveWbCalculation() {
            if (!this.wbConfig || this.wbSaving) return;
            this.wbSaving = true;
            const { ok, data } = await apiRequest('/api/wb-calculations/', {
                method: 'POST',
                body: JSON.stringify({
                    aircraft: `/api/aircraft/${this.aircraftId}/`,
                    label: this.wbCalcLabel.trim() || 'Unnamed scenario',
                    items: this.wbItems.map(item => ({
                        station_name: item.station_name,
                        arm: item.arm,
                        weight: parseFloat(item.weight) || 0,
                    })),
                    empty_weight: this.wbConfig.empty_weight,
                    empty_cg: this.wbConfig.empty_cg,
                    notes: this.wbCalcNotes.trim(),
                }),
            });
            if (ok) {
                this.wbCalculations.unshift(data);
                this.wbCalcLabel = '';
                this.wbCalcNotes = '';
                showNotification('W&B calculation saved', 'success');
            } else {
                showNotification('Failed to save calculation', 'danger');
            }
            this.wbSaving = false;
        },

        async loadWbCalculations() {
            const { ok, data } = await apiRequest(
                `/api/wb-calculations/?aircraft=${this.aircraftId}`
            );
            if (ok) {
                this.wbCalculations = Array.isArray(data) ? data : (data.results || []);
            }
            this.wbCalcsLoaded = true;
        },

        /** Load a previously saved scenario back into the live calculator. */
        wbLoadIntoCalculator(calc) {
            this.wbItems = calc.items.map(item => ({
                station_name: item.station_name,
                arm: parseFloat(item.arm),
                weight: parseFloat(item.weight),
            }));
            this.wbCalcLabel = calc.label;
            this.wbCalcNotes = calc.notes || '';
            showNotification('Scenario loaded — edit and re-save as needed', 'info');
        },

        async deleteWbCalculation(id) {
            const { ok } = await apiRequest(`/api/wb-calculations/${id}/`, {
                method: 'DELETE',
            });
            if (ok) {
                this.wbCalculations = this.wbCalculations.filter(c => c.id !== id);
                this.wbDeleteConfirmId = null;
                showNotification('Calculation deleted', 'success');
            }
        },

        // ----------------------------------------------------------------
        // Config editor modal
        // ----------------------------------------------------------------

        openWbConfigModal() {
            if (this.wbConfig) {
                // Edit existing — copy all fields into the form
                this.wbConfigForm = {
                    empty_weight: this.wbConfig.empty_weight,
                    empty_cg: this.wbConfig.empty_cg,
                    max_gross_weight: this.wbConfig.max_gross_weight,
                    fwd_cg_limit: this.wbConfig.fwd_cg_limit,
                    aft_cg_limit: this.wbConfig.aft_cg_limit,
                    // Deep-copy stations so edits don't mutate the live config
                    stations: (this.wbConfig.stations || []).map(s => ({ ...s })),
                    notes: this.wbConfig.notes || '',
                };
            } else {
                // New config — seed with sensible placeholder station names
                this.wbConfigForm = {
                    empty_weight: '',
                    empty_cg: '',
                    max_gross_weight: '',
                    fwd_cg_limit: '',
                    aft_cg_limit: '',
                    stations: [
                        { name: 'Front Seats', arm: '' },
                        { name: 'Rear Seats', arm: '' },
                        { name: 'Baggage', arm: '' },
                        { name: 'Fuel (gal × 6.0 lbs)', arm: '' },
                    ],
                    notes: '',
                };
            }
            this.wbConfigModalOpen = true;
        },

        closeWbConfigModal() {
            this.wbConfigModalOpen = false;
        },

        wbAddStation() {
            this.wbConfigForm.stations.push({ name: '', arm: '' });
        },

        wbRemoveStation(index) {
            this.wbConfigForm.stations.splice(index, 1);
        },

        async saveWbConfig() {
            if (this.wbConfigSaving) return;
            this.wbConfigSaving = true;

            const payload = {
                aircraft: `/api/aircraft/${this.aircraftId}/`,
                empty_weight: this.wbConfigForm.empty_weight,
                empty_cg: this.wbConfigForm.empty_cg,
                max_gross_weight: this.wbConfigForm.max_gross_weight,
                fwd_cg_limit: this.wbConfigForm.fwd_cg_limit,
                aft_cg_limit: this.wbConfigForm.aft_cg_limit,
                stations: this.wbConfigForm.stations.filter(s => s.name.trim()),
                notes: this.wbConfigForm.notes,
            };

            let ok, data;
            if (this.wbConfig) {
                ({ ok, data } = await apiRequest(`/api/wb-configs/${this.wbConfig.id}/`, {
                    method: 'PATCH',
                    body: JSON.stringify(payload),
                }));
            } else {
                ({ ok, data } = await apiRequest('/api/wb-configs/', {
                    method: 'POST',
                    body: JSON.stringify(payload),
                }));
            }

            if (ok) {
                this.wbConfig = data;
                this._resetWbItems();
                this.closeWbConfigModal();
                showNotification('W&B configuration saved', 'success');
            } else {
                showNotification('Failed to save configuration', 'danger');
            }
            this.wbConfigSaving = false;
        },

        // ----------------------------------------------------------------
        // Formatting helpers
        // ----------------------------------------------------------------

        wbFmt(value, decimals = 1) {
            const n = parseFloat(value);
            return isNaN(n) ? '—' : n.toFixed(decimals);
        },
    };
});
