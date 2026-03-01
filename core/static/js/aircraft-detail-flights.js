function flightsMixin() {
    const emptyForm = () => ({
        date: new Date().toISOString().split('T')[0],
        tach_time: '',
        tach_out: '',
        tach_in: '',
        hobbs_time: '',
        hobbs_out: '',
        hobbs_in: '',
        departure_location: '',
        destination_location: '',
        route: '',
        oil_added: '',
        oil_added_type: '',
        oil_level_after: '',
        fuel_added: '',
        fuel_added_type: '',
        fuel_level_after: '',
        notes: '',
    });

    return {
        flightLogs: [],
        flightLogsLoaded: false,
        flightLogModalOpen: false,
        flightLogSubmitting: false,
        editingFlightLog: null,
        flightLogForm: emptyForm(),
        flightLogDeleteConfirmOpen: false,
        flightLogDeleteTarget: null,
        flightLogTrackFile: null,

        get computedTachTime() {
            const out = parseFloat(this.flightLogForm.tach_out);
            const inVal = parseFloat(this.flightLogForm.tach_in);
            if (!isNaN(out) && !isNaN(inVal) && inVal > out) {
                return (inVal - out).toFixed(1);
            }
            return null;
        },

        get computedHobbsTime() {
            const out = parseFloat(this.flightLogForm.hobbs_out);
            const inVal = parseFloat(this.flightLogForm.hobbs_in);
            if (!isNaN(out) && !isNaN(inVal) && inVal > out) {
                return (inVal - out).toFixed(1);
            }
            return null;
        },

        async loadFlightLogs() {
            if (!this.aircraft) return;
            try {
                const { ok, data } = await apiRequest(`/api/aircraft/${this.aircraft.id}/flight_logs/`);
                if (ok) {
                    this.flightLogs = data.flight_logs || [];
                    this.flightLogsLoaded = true;
                }
            } catch (e) {
                console.error('Error loading flight logs:', e);
            }
        },

        openFlightLogModal(flightLog = null) {
            this.editingFlightLog = flightLog;
            if (flightLog) {
                this.flightLogForm = {
                    date: flightLog.date || '',
                    tach_time: flightLog.tach_time || '',
                    tach_out: flightLog.tach_out || '',
                    tach_in: flightLog.tach_in || '',
                    hobbs_time: flightLog.hobbs_time || '',
                    hobbs_out: flightLog.hobbs_out || '',
                    hobbs_in: flightLog.hobbs_in || '',
                    departure_location: flightLog.departure_location || '',
                    destination_location: flightLog.destination_location || '',
                    route: flightLog.route || '',
                    oil_added: flightLog.oil_added || '',
                    oil_added_type: flightLog.oil_added_type || '',
                    oil_level_after: flightLog.oil_level_after || '',
                    fuel_added: flightLog.fuel_added || '',
                    fuel_added_type: flightLog.fuel_added_type || '',
                    fuel_level_after: flightLog.fuel_level_after || '',
                    notes: flightLog.notes || '',
                };
            } else {
                this.flightLogForm = emptyForm();
                // Pre-fill tach_out from current meter reading
                if (this.aircraft) {
                    const tachOffset = parseFloat(this.aircraft.tach_time_offset) || 0;
                    const currentReading = (parseFloat(this.aircraft.tach_time) || 0) - tachOffset;
                    this.flightLogForm.tach_out = currentReading.toFixed(1);
                }
            }
            this.flightLogTrackFile = null;
            this.flightLogModalOpen = true;
        },

        closeFlightLogModal() {
            this.flightLogModalOpen = false;
            this.editingFlightLog = null;
            this.flightLogTrackFile = null;
        },

        handleFlightTrackFileChange(event) {
            const file = event.target.files[0];
            if (file) {
                this.flightLogTrackFile = file;
            }
        },

        async submitFlightLog() {
            if (this.flightLogSubmitting) return;
            if (!this.flightLogForm.date || !this.flightLogForm.tach_time) {
                showNotification('Date and Tach Time are required', 'warning');
                return;
            }
            if (this.flightLogForm.oil_added && !this.flightLogForm.oil_level_after) {
                showNotification('Oil level after addition is required when oil is added', 'warning');
                return;
            }
            if (this.flightLogForm.fuel_added && !this.flightLogForm.fuel_level_after) {
                showNotification('Fuel level after addition is required when fuel is added', 'warning');
                return;
            }

            this.flightLogSubmitting = true;
            try {
                let response;
                if (this.editingFlightLog) {
                    // PATCH — JSON request (no file changes via the edit form for simplicity)
                    const body = {};
                    const fields = ['date', 'tach_time', 'tach_out', 'tach_in',
                                    'hobbs_time', 'hobbs_out', 'hobbs_in',
                                    'departure_location', 'destination_location', 'route',
                                    'oil_added', 'oil_added_type', 'oil_level_after',
                                    'fuel_added', 'fuel_added_type', 'fuel_level_after', 'notes'];
                    for (const f of fields) {
                        const v = this.flightLogForm[f];
                        body[f] = (v === '' || v === null) ? null : v;
                    }
                    const result = await apiRequest(
                        `/api/flight-logs/${this.editingFlightLog.id}/`,
                        { method: 'PATCH', body: JSON.stringify(body) }
                    );
                    if (result.ok) {
                        showNotification('Flight log updated', 'success');
                        await this.loadFlightLogs();
                        this.closeFlightLogModal();
                    } else {
                        showNotification(formatApiError(result.data, 'Failed to update flight log'), 'danger');
                    }
                } else {
                    // POST — FormData to support optional KML upload
                    const fd = new FormData();
                    fd.append('aircraft', this.aircraft.id);
                    const fields = ['date', 'tach_time', 'tach_out', 'tach_in',
                                    'hobbs_time', 'hobbs_out', 'hobbs_in',
                                    'departure_location', 'destination_location', 'route',
                                    'oil_added', 'oil_added_type', 'oil_level_after',
                                    'fuel_added', 'fuel_added_type', 'fuel_level_after', 'notes'];
                    for (const f of fields) {
                        const v = this.flightLogForm[f];
                        if (v !== '' && v !== null && v !== undefined) {
                            fd.append(f, v);
                        }
                    }
                    if (this.flightLogTrackFile) {
                        fd.append('track_log', this.flightLogTrackFile);
                    }
                    response = await fetch(`/api/aircraft/${this.aircraft.id}/flight_logs/`, {
                        method: 'POST',
                        headers: { 'X-CSRFToken': getCookie('csrftoken') },
                        body: fd,
                    });
                    if (response.ok) {
                        showNotification('Flight logged successfully', 'success');
                        await this.loadFlightLogs();
                        await this.loadData();  // refresh aircraft totals
                        this.closeFlightLogModal();
                    } else {
                        const errData = await response.json().catch(() => ({}));
                        showNotification(formatApiError(errData, 'Failed to log flight'), 'danger');
                    }
                }
            } catch (e) {
                console.error('Error submitting flight log:', e);
                showNotification('Error saving flight log', 'danger');
            } finally {
                this.flightLogSubmitting = false;
            }
        },

        openFlightLogDeleteConfirm(flightLog) {
            this.flightLogDeleteTarget = flightLog;
            this.flightLogDeleteConfirmOpen = true;
        },

        closeFlightLogDeleteConfirm() {
            this.flightLogDeleteConfirmOpen = false;
            this.flightLogDeleteTarget = null;
        },

        async deleteFlightLog() {
            if (!this.flightLogDeleteTarget) return;
            try {
                const { ok } = await apiRequest(
                    `/api/flight-logs/${this.flightLogDeleteTarget.id}/`,
                    { method: 'DELETE' }
                );
                if (ok) {
                    showNotification('Flight log deleted', 'success');
                    await this.loadFlightLogs();
                    await this.loadData();  // refresh aircraft totals
                } else {
                    showNotification('Failed to delete flight log', 'danger');
                }
            } catch (e) {
                console.error('Error deleting flight log:', e);
                showNotification('Error deleting flight log', 'danger');
            } finally {
                this.closeFlightLogDeleteConfirm();
            }
        },

        formatFlightRoute(log) {
            if (log.departure_location && log.destination_location) {
                return `${log.departure_location} → ${log.destination_location}`;
            }
            return log.route || '—';
        },
    };
}
