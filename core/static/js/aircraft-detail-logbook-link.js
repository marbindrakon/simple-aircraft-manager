function logbookLinkMixin() {
    return {
        linkPickerOpen: false,
        linkPickerEntry: null,        // the logbook entry being linked FROM
        linkPickerTab: 'inspections', // 'inspections' | 'ads' | 'major_records'
        linkPickerSubmitting: false,

        // Inspection records that have no logbook entry linked yet.
        // Derives from already-loaded inspectionTypes — no extra API calls.
        get linkableInspections() {
            return (this.inspectionTypes || [])
                .filter(t => t.latest_record && !t.latest_record.logbook_entry)
                .map(t => ({
                    id: t.latest_record.id,
                    label: t.name,
                    date: t.latest_record.date,
                    hours: t.latest_record.aircraft_hours,
                    type: 'inspection',
                }));
        },

        // AD compliance records that have no logbook entry linked yet.
        // Surfaces only latest_compliance per AD (MVP limitation).
        get linkableAdCompliances() {
            return (this.applicableAds || [])
                .filter(ad => ad.latest_compliance && !ad.latest_compliance.logbook_entry)
                .map(ad => ({
                    id: ad.latest_compliance.id,
                    label: ad.name,
                    date: ad.latest_compliance.date_complied,
                    hours: ad.latest_compliance.aircraft_hours_at_compliance,
                    type: 'compliance',
                }));
        },

        // Major records that have no logbook entry linked yet.
        get linkableMajorRecords() {
            return (this.majorRecords || [])
                .filter(r => !r.logbook_entry)
                .map(r => ({
                    id: r.id,
                    label: r.title,
                    date: r.date_performed,
                    hours: r.aircraft_hours,
                    type: 'major_record',
                }));
        },

        openLinkPicker(entry) {
            this.linkPickerEntry = entry;
            // Trigger lazy loads for data that might not be loaded yet
            if (!this.inspectionsLoaded) this.loadInspections();
            if (!this.adsLoaded) this.loadAds();
            if (!this.majorRecordsLoaded) this.loadMajorRecords();
            // Default to inspections tab; user can switch if empty
            this.linkPickerTab = 'inspections';
            this.linkPickerOpen = true;
        },

        async linkEntryTo(record) {
            if (this.linkPickerSubmitting || !this.linkPickerEntry) return;
            this.linkPickerSubmitting = true;
            try {
                const endpointMap = {
                    compliance: `/api/ad-compliances/${record.id}/`,
                    inspection: `/api/inspections/${record.id}/`,
                    major_record: `/api/major-records/${record.id}/`,
                };
                const url = endpointMap[record.type];
                if (!url) return;

                const response = await apiRequest(url, {
                    method: 'PATCH',
                    body: JSON.stringify({ logbook_entry: this.linkPickerEntry.id }),
                });

                if (response.ok) {
                    showNotification('Logbook entry linked', 'success');
                    this.linkPickerOpen = false;
                    // Refresh affected data type
                    if (record.type === 'compliance') {
                        this.adsLoaded = false;
                        await this.loadAds();
                    } else if (record.type === 'inspection') {
                        this.inspectionsLoaded = false;
                        await this.loadInspections();
                    } else if (record.type === 'major_record') {
                        await this.loadMajorRecords();
                    }
                } else {
                    showNotification(formatApiError(response.data, 'Failed to link entry'), 'danger');
                }
            } catch (error) {
                console.error('Error linking logbook entry:', error);
                showNotification('Error linking logbook entry', 'danger');
            } finally {
                this.linkPickerSubmitting = false;
            }
        },
    };
}
