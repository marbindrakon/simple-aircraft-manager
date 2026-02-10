function aircraftDetail(aircraftId) {
    return {
        aircraftId: aircraftId,
        aircraft: null,
        components: [],
        recentLogs: [],
        activeSquawks: [],
        loading: true,
        activeTab: 'overview',

        // Documents state
        documentCollections: [],
        uncollectedDocuments: [],
        documentsLoading: false,
        documentsLoaded: false,

        // Document viewer state
        viewerOpen: false,
        viewerDocument: null,
        viewerCollectionName: '',
        viewerImageIndex: 0,

        // Collection modal state
        collectionModalOpen: false,
        editingCollection: null,
        collectionSubmitting: false,
        collectionForm: {
            name: '',
            description: '',
        },

        // Document modal state
        documentModalOpen: false,
        editingDocument: null,
        documentSubmitting: false,
        documentForm: {
            name: '',
            description: '',
            doc_type: 'OTHER',
            collection: '',
        },
        documentImageFiles: [],
        documentTypes: [
            { value: 'LOG', label: 'Logbook' },
            { value: 'ALTER', label: 'Alteration Record' },
            { value: 'REPORT', label: 'Report' },
            { value: 'ESTIMATE', label: 'Estimate' },
            { value: 'DISC', label: 'Discrepancy List' },
            { value: 'INVOICE', label: 'Receipt / Invoice' },
            { value: 'AIRCRAFT', label: 'Aircraft Record' },
            { value: 'OTHER', label: 'Other' },
        ],

        // Squawk modal state
        squawkModalOpen: false,
        editingSquawk: null,
        squawkSubmitting: false,
        squawkForm: {
            priority: 1,
            component: '',
            issue_reported: '',
            notes: '',
        },

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

        // Component modal state
        componentModalOpen: false,
        editingComponent: null,
        componentSubmitting: false,
        componentTypes: [],
        componentTypesLoaded: false,
        componentForm: {
            parent_component: '',
            component_type: '',
            manufacturer: '',
            model: '',
            serial_number: '',
            install_location: '',
            notes: '',
            status: 'IN-USE',
            date_in_service: '',
            hours_in_service: 0,
            hours_since_overhaul: 0,
            overhaul_date: '',
            tbo_hours: '',
            tbo_days: '',
            inspection_hours: '',
            inspection_days: '',
            replacement_hours: '',
            replacement_days: '',
            tbo_critical: true,
            inspection_critical: true,
            replacement_critical: false,
        },

        // AD tracking state
        applicableAds: [],
        allAds: [],
        adsLoaded: false,
        adModalOpen: false,
        complianceModalOpen: false,
        selectedAd: null,
        editingAd: null,
        selectedExistingAdId: '',
        adSubmitting: false,
        complianceSubmitting: false,
        adForm: {
            name: '',
            short_description: '',
            required_action: '',
            recurring: false,
            recurring_hours: 0,
            recurring_months: 0,
            recurring_days: 0,
        },
        complianceForm: {
            date_complied: '',
            compliance_notes: '',
            permanent: false,
            next_due_at_time: '',
        },

        // Notes state
        aircraftNotes: [],
        showAllNotes: false,
        noteModalOpen: false,
        editingNote: null,
        noteSubmitting: false,
        noteForm: {
            text: '',
        },

        async init() {
            await this.loadData();

            // Watch for tab changes to load data lazily
            this.$watch('activeTab', (tab) => {
                if (tab === 'documents' && !this.documentsLoaded) {
                    this.loadDocuments();
                }
                if (tab === 'ads' && !this.adsLoaded) {
                    this.loadAds();
                }
                if (tab === 'oil' && !this.oilLoaded) {
                    this.loadOilRecords();
                }
                if (tab === 'fuel' && !this.fuelLoaded) {
                    this.loadFuelRecords();
                }
            });
        },

        async loadData() {
            this.loading = true;
            try {
                // Load aircraft summary with all related data
                const response = await fetch(`/api/aircraft/${this.aircraftId}/summary/`);
                const data = await response.json();

                this.aircraft = data.aircraft;
                this.components = data.components;
                this.recentLogs = data.recent_logs;
                this.activeSquawks = data.active_squawks;
                this.aircraftNotes = data.notes || [];
            } catch (error) {
                console.error('Error loading aircraft data:', error);
                showNotification('Failed to load aircraft data', 'danger');
            } finally {
                this.loading = false;
            }
        },

        async loadDocuments() {
            if (this.documentsLoading) return;

            this.documentsLoading = true;
            try {
                const response = await fetch(`/api/aircraft/${this.aircraftId}/documents/`);
                const data = await response.json();

                this.documentCollections = data.collections || [];
                this.uncollectedDocuments = data.uncollected_documents || [];
                this.documentsLoaded = true;
            } catch (error) {
                console.error('Error loading documents:', error);
                showNotification('Failed to load documents', 'danger');
            } finally {
                this.documentsLoading = false;
            }
        },

        openHoursModal() {
            window.dispatchEvent(new CustomEvent('open-hours-modal', {
                detail: { aircraft: this.aircraft }
            }));
        },

        // Document file type helpers
        getFileType(url) {
            if (!url) return 'unknown';
            const ext = url.split('.').pop().toLowerCase().split('?')[0];
            if (['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'tiff'].includes(ext)) return 'image';
            if (ext === 'pdf') return 'pdf';
            if (['txt', 'text'].includes(ext)) return 'text';
            return 'unknown';
        },

        getFileIcon(url) {
            const type = this.getFileType(url);
            switch (type) {
                case 'pdf': return 'fas fa-file-pdf';
                case 'text': return 'fas fa-file-alt';
                default: return 'fas fa-file';
            }
        },

        // Document viewer methods
        openDocumentViewer(doc, collectionName) {
            this.viewerDocument = doc;
            this.viewerCollectionName = collectionName;
            this.viewerImageIndex = 0;
            this.viewerOpen = true;
        },

        closeDocumentViewer() {
            this.viewerOpen = false;
            this.viewerDocument = null;
            this.viewerCollectionName = '';
            this.viewerImageIndex = 0;
        },

        nextImage() {
            if (this.viewerDocument?.images && this.viewerImageIndex < this.viewerDocument.images.length - 1) {
                this.viewerImageIndex++;
            }
        },

        prevImage() {
            if (this.viewerImageIndex > 0) {
                this.viewerImageIndex--;
            }
        },

        formatHours(hours) {
            return parseFloat(hours || 0).toFixed(1);
        },

        formatDate(dateString) {
            return new Date(dateString).toLocaleDateString();
        },

        getComponentTypeName(component) {
            return component.component_type_name || 'Unknown';
        },

        calculateHoursToTBO(component) {
            if (!component.tbo_hours) {
                return 'N/A';
            }
            const remaining = component.tbo_hours - (component.hours_since_overhaul || 0);
            return remaining > 0 ? remaining.toFixed(1) : '0.0';
        },

        getComponentCurrentHours(component) {
            // Show hours_in_service for replacement_critical, otherwise hours_since_overhaul
            if (component.replacement_critical) {
                return component.hours_in_service || 0;
            }
            return component.hours_since_overhaul || 0;
        },

        getComponentInterval(component) {
            // Show replacement interval for replacement_critical, otherwise TBO
            if (component.replacement_critical && component.replacement_hours) {
                return component.replacement_hours + ' hrs';
            }
            if (component.tbo_hours) {
                return component.tbo_hours + ' hrs';
            }
            return 'N/A';
        },

        calculateHoursRemaining(component) {
            // Calculate remaining hours based on component type
            let interval = null;
            let currentHours = 0;

            if (component.replacement_critical && component.replacement_hours) {
                interval = component.replacement_hours;
                currentHours = component.hours_in_service || 0;
            } else if (component.tbo_hours) {
                interval = component.tbo_hours;
                currentHours = component.hours_since_overhaul || 0;
            }

            if (!interval) {
                return 'N/A';
            }

            const remaining = interval - currentHours;
            return remaining > 0 ? remaining.toFixed(1) : '0.0';
        },

        getHoursRemainingClass(component) {
            const remaining = this.calculateHoursRemaining(component);
            if (remaining === 'N/A') return '';

            const hours = parseFloat(remaining);
            if (hours <= 0) {
                return 'hours-overdue';
            } else if (hours < 10) {
                return 'hours-critical';
            } else if (hours < 25) {
                return 'hours-warning';
            }
            return '';
        },

        async resetComponentService(component) {
            const typeName = this.getComponentTypeName(component);
            if (!confirm(`Reset service time for ${typeName}?\n\nThis will set hours since service to 0 and update the service date to today.`)) {
                return;
            }

            try {
                const response = await fetch(`/api/component/${component.id}/reset_service/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                });

                if (response.ok) {
                    const data = await response.json();
                    showNotification(`${typeName} service reset - was ${data.old_hours} hrs`, 'success');
                    await this.loadData(); // Reload to get updated component data
                } else {
                    showNotification('Failed to reset service time', 'danger');
                }
            } catch (error) {
                console.error('Error resetting service:', error);
                showNotification('Error resetting service time', 'danger');
            }
        },

        // Component CRUD methods
        async loadComponentTypes() {
            if (this.componentTypesLoaded) return;
            try {
                const response = await fetch('/api/component-type/');
                const data = await response.json();
                this.componentTypes = data.results || data;
                this.componentTypesLoaded = true;
            } catch (error) {
                console.error('Error loading component types:', error);
                showNotification('Failed to load component types', 'danger');
            }
        },

        openComponentModal() {
            this.editingComponent = null;
            this.componentForm = {
                parent_component: '',
                component_type: '',
                manufacturer: '',
                model: '',
                serial_number: '',
                install_location: '',
                notes: '',
                status: 'IN-USE',
                date_in_service: new Date().toISOString().split('T')[0],
                hours_in_service: 0,
                hours_since_overhaul: 0,
                overhaul_date: '',
                tbo_hours: '',
                tbo_days: '',
                inspection_hours: '',
                inspection_days: '',
                replacement_hours: '',
                replacement_days: '',
                tbo_critical: true,
                inspection_critical: true,
                replacement_critical: false,
            };
            this.loadComponentTypes();
            this.componentModalOpen = true;
        },

        editComponent(component) {
            this.editingComponent = component;
            this.componentForm = {
                parent_component: component.parent_component_id || '',
                component_type: component.component_type_id || component.component_type,
                manufacturer: component.manufacturer || '',
                model: component.model || '',
                serial_number: component.serial_number || '',
                install_location: component.install_location || '',
                notes: component.notes || '',
                status: component.status || 'IN-USE',
                date_in_service: component.date_in_service || '',
                hours_in_service: component.hours_in_service || 0,
                hours_since_overhaul: component.hours_since_overhaul || 0,
                overhaul_date: component.overhaul_date || '',
                tbo_hours: component.tbo_hours || '',
                tbo_days: component.tbo_days || '',
                inspection_hours: component.inspection_hours || '',
                inspection_days: component.inspection_days || '',
                replacement_hours: component.replacement_hours || '',
                replacement_days: component.replacement_days || '',
                tbo_critical: component.tbo_critical ?? true,
                inspection_critical: component.inspection_critical ?? true,
                replacement_critical: component.replacement_critical ?? false,
            };
            this.loadComponentTypes();
            this.componentModalOpen = true;
        },

        closeComponentModal() {
            this.componentModalOpen = false;
            this.editingComponent = null;
        },

        async submitComponent() {
            if (this.componentSubmitting) return;

            this.componentSubmitting = true;
            try {
                const data = {
                    component_type: this.componentForm.component_type,
                    manufacturer: this.componentForm.manufacturer,
                    model: this.componentForm.model,
                    serial_number: this.componentForm.serial_number,
                    install_location: this.componentForm.install_location,
                    notes: this.componentForm.notes,
                    status: this.componentForm.status,
                    date_in_service: this.componentForm.date_in_service,
                    hours_in_service: parseFloat(this.componentForm.hours_in_service) || 0,
                    hours_since_overhaul: parseFloat(this.componentForm.hours_since_overhaul) || 0,
                    tbo_critical: this.componentForm.tbo_critical,
                    inspection_critical: this.componentForm.inspection_critical,
                    replacement_critical: this.componentForm.replacement_critical,
                };

                // Only include optional fields if they have values
                if (this.componentForm.parent_component) {
                    data.parent_component = this.componentForm.parent_component;
                } else {
                    data.parent_component = null;
                }
                if (this.componentForm.overhaul_date) data.overhaul_date = this.componentForm.overhaul_date;
                if (this.componentForm.tbo_hours) data.tbo_hours = parseInt(this.componentForm.tbo_hours);
                if (this.componentForm.tbo_days) data.tbo_days = parseInt(this.componentForm.tbo_days);
                if (this.componentForm.inspection_hours) data.inspection_hours = parseInt(this.componentForm.inspection_hours);
                if (this.componentForm.inspection_days) data.inspection_days = parseInt(this.componentForm.inspection_days);
                if (this.componentForm.replacement_hours) data.replacement_hours = parseInt(this.componentForm.replacement_hours);
                if (this.componentForm.replacement_days) data.replacement_days = parseInt(this.componentForm.replacement_days);

                let response;
                if (this.editingComponent) {
                    response = await fetch(`/api/component/${this.editingComponent.id}/`, {
                        method: 'PATCH',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': getCookie('csrftoken'),
                        },
                        body: JSON.stringify(data),
                    });
                } else {
                    response = await fetch(`/api/aircraft/${this.aircraftId}/components/`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': getCookie('csrftoken'),
                        },
                        body: JSON.stringify(data),
                    });
                }

                if (response.ok) {
                    showNotification(
                        this.editingComponent ? 'Component updated' : 'Component added',
                        'success'
                    );
                    this.closeComponentModal();
                    await this.loadData();
                } else {
                    const errorData = await response.json();
                    const msg = typeof errorData === 'object'
                        ? Object.values(errorData).flat().join(', ')
                        : 'Failed to save component';
                    showNotification(msg, 'danger');
                }
            } catch (error) {
                console.error('Error saving component:', error);
                showNotification('Error saving component', 'danger');
            } finally {
                this.componentSubmitting = false;
            }
        },

        async deleteComponent(component) {
            const typeName = this.getComponentTypeName(component);
            if (!confirm(`Delete ${typeName}${component.install_location ? ' (' + component.install_location + ')' : ''}?\n\nThis action cannot be undone.`)) {
                return;
            }

            try {
                const response = await fetch(`/api/component/${component.id}/`, {
                    method: 'DELETE',
                    headers: {
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                });

                if (response.ok || response.status === 204) {
                    showNotification(`${typeName} deleted`, 'success');
                    await this.loadData();
                } else {
                    showNotification('Failed to delete component', 'danger');
                }
            } catch (error) {
                console.error('Error deleting component:', error);
                showNotification('Error deleting component', 'danger');
            }
        },

        getComponentLabel(component) {
            let label = this.getComponentTypeName(component);
            if (component.install_location) {
                label += ` (${component.install_location})`;
            }
            return label;
        },

        getComponentDepth(component) {
            if (!component.parent_component_id) return 0;
            const parent = this.components.find(c => c.id === component.parent_component_id);
            if (!parent) return 0;
            return 1 + this.getComponentDepth(parent);
        },

        get sortedComponents() {
            // Build a tree-sorted list: parents followed by their children
            const roots = this.components.filter(c => !c.parent_component_id);
            const result = [];

            const addWithChildren = (component) => {
                result.push(component);
                const children = this.components.filter(c => c.parent_component_id === component.id);
                children.forEach(child => addWithChildren(child));
            };

            roots.forEach(root => addWithChildren(root));

            // Add any orphans (parent not in this aircraft's components)
            const added = new Set(result.map(c => c.id));
            this.components.forEach(c => {
                if (!added.has(c.id)) result.push(c);
            });

            return result;
        },

        getParentOptions(excludeId) {
            // Return components that can be parents (exclude self and descendants)
            if (!excludeId) return this.components;

            const descendants = new Set();
            const collectDescendants = (id) => {
                descendants.add(id);
                this.components.filter(c => c.parent_component_id === id).forEach(c => collectDescendants(c.id));
            };
            collectDescendants(excludeId);

            return this.components.filter(c => !descendants.has(c.id));
        },

        getStatusClass(component) {
            if (component.status === 'IN-USE') {
                // Check if due for service
                const hoursToTBO = this.calculateHoursToTBO(component);
                if (hoursToTBO !== 'N/A') {
                    const hours = parseFloat(hoursToTBO);
                    if (hours <= 0) {
                        return 'pf-m-red'; // Overdue
                    } else if (hours < 50) {
                        return 'pf-m-orange'; // Due soon
                    }
                }
                return 'pf-m-green'; // Serviceable
            } else if (component.status === 'SPARE') {
                return 'pf-m-blue';
            } else if (component.status === 'DISPOSED') {
                return 'pf-m-red';
            }
            return 'pf-m-grey';
        },

        // Airworthiness status helpers
        getAirworthinessClass() {
            const status = this.aircraft?.airworthiness?.status || 'GREEN';
            switch (status) {
                case 'RED':
                    return 'airworthiness-red';
                case 'ORANGE':
                    return 'airworthiness-orange';
                default:
                    return 'airworthiness-green';
            }
        },

        getAirworthinessText() {
            const status = this.aircraft?.airworthiness?.status || 'GREEN';
            switch (status) {
                case 'RED':
                    return 'Grounded';
                case 'ORANGE':
                    return 'Caution';
                default:
                    return 'Airworthy';
            }
        },

        getAirworthinessTooltip() {
            const aw = this.aircraft?.airworthiness;
            if (!aw || aw.status === 'GREEN') {
                return 'Aircraft is airworthy';
            }

            const issues = aw.issues || [];
            if (issues.length === 0) {
                return aw.status === 'RED' ? 'Aircraft is grounded' : 'Maintenance due soon';
            }

            return issues.map(i => `${i.category}: ${i.title}`).join('\n');
        },

        // Squawk management methods
        openSquawkModal() {
            this.editingSquawk = null;
            this.squawkForm = {
                priority: 1,
                component: '',
                issue_reported: '',
                notes: '',
            };
            this.squawkModalOpen = true;
        },

        editSquawk(squawk) {
            this.editingSquawk = squawk;
            this.squawkForm = {
                priority: squawk.priority,
                component: squawk.component || '',
                issue_reported: squawk.issue_reported,
                notes: squawk.notes || '',
            };
            this.squawkModalOpen = true;
        },

        closeSquawkModal() {
            this.squawkModalOpen = false;
            this.editingSquawk = null;
            this.squawkForm = {
                priority: 1,
                component: '',
                issue_reported: '',
                notes: '',
            };
        },

        async submitSquawk() {
            if (this.squawkSubmitting) return;

            this.squawkSubmitting = true;
            try {
                const data = {
                    priority: parseInt(this.squawkForm.priority),
                    issue_reported: this.squawkForm.issue_reported,
                    notes: this.squawkForm.notes,
                };

                // Only include component if selected
                if (this.squawkForm.component) {
                    data.component = this.squawkForm.component;
                }

                let response;
                if (this.editingSquawk) {
                    // Update existing squawk
                    response = await fetch(`/api/squawks/${this.editingSquawk.id}/`, {
                        method: 'PATCH',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': getCookie('csrftoken'),
                        },
                        body: JSON.stringify(data),
                    });
                } else {
                    // Create new squawk
                    response = await fetch(`/api/aircraft/${this.aircraftId}/squawks/`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': getCookie('csrftoken'),
                        },
                        body: JSON.stringify(data),
                    });
                }

                if (response.ok) {
                    showNotification(
                        this.editingSquawk ? 'Squawk updated' : 'Squawk created',
                        'success'
                    );
                    this.closeSquawkModal();
                    await this.loadData(); // Reload to get updated squawks
                } else {
                    const errorData = await response.json();
                    showNotification(errorData.detail || 'Failed to save squawk', 'danger');
                }
            } catch (error) {
                console.error('Error saving squawk:', error);
                showNotification('Error saving squawk', 'danger');
            } finally {
                this.squawkSubmitting = false;
            }
        },

        async resolveSquawk(squawk) {
            if (!confirm('Mark this squawk as resolved?')) return;

            try {
                const response = await fetch(`/api/squawks/${squawk.id}/`, {
                    method: 'PATCH',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                    body: JSON.stringify({ resolved: true }),
                });

                if (response.ok) {
                    showNotification('Squawk resolved', 'success');
                    await this.loadData(); // Reload to update squawk list
                } else {
                    showNotification('Failed to resolve squawk', 'danger');
                }
            } catch (error) {
                console.error('Error resolving squawk:', error);
                showNotification('Error resolving squawk', 'danger');
            }
        },

        getSquawkPriorityClass(squawk) {
            switch (squawk.priority) {
                case 0:
                    return 'pf-m-red';
                case 1:
                    return 'pf-m-orange';
                case 2:
                    return 'pf-m-blue';
                default:
                    return 'pf-m-grey';
            }
        },

        getSquawkCardClass(squawk) {
            switch (squawk.priority) {
                case 0:
                    return 'card-border-red';
                case 1:
                    return 'card-border-orange';
                default:
                    return '';
            }
        },

        formatDateTime(dateString) {
            return new Date(dateString).toLocaleString();
        },

        // Note management methods
        openNoteModal() {
            this.editingNote = null;
            this.noteForm = { text: '' };
            this.noteModalOpen = true;
        },

        editNote(note) {
            this.editingNote = note;
            this.noteForm = { text: note.text };
            this.noteModalOpen = true;
        },

        closeNoteModal() {
            this.noteModalOpen = false;
            this.editingNote = null;
            this.noteForm = { text: '' };
        },

        async submitNote() {
            if (this.noteSubmitting) return;
            if (!this.noteForm.text.trim()) {
                showNotification('Note text is required', 'warning');
                return;
            }

            this.noteSubmitting = true;
            try {
                const data = { text: this.noteForm.text };

                let response;
                if (this.editingNote) {
                    // Update existing note
                    response = await fetch(`/api/aircraft-notes/${this.editingNote.id}/`, {
                        method: 'PATCH',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': getCookie('csrftoken'),
                        },
                        body: JSON.stringify(data),
                    });
                } else {
                    // Create new note
                    response = await fetch(`/api/aircraft/${this.aircraftId}/notes/`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': getCookie('csrftoken'),
                        },
                        body: JSON.stringify(data),
                    });
                }

                if (response.ok) {
                    showNotification(
                        this.editingNote ? 'Note updated' : 'Note added',
                        'success'
                    );
                    this.closeNoteModal();
                    await this.loadData();
                } else {
                    const errorData = await response.json();
                    showNotification(errorData.detail || 'Failed to save note', 'danger');
                }
            } catch (error) {
                console.error('Error saving note:', error);
                showNotification('Error saving note', 'danger');
            } finally {
                this.noteSubmitting = false;
            }
        },

        // Oil record methods
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

            // Sort by flight_hours ascending for charting
            const sorted = [...this.oilRecords].sort((a, b) => parseFloat(a.flight_hours) - parseFloat(b.flight_hours));

            // Calculate hours per quart between consecutive records
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

        // Fuel record methods
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

            // Sort by flight_hours ascending for charting
            const sorted = [...this.fuelRecords].sort((a, b) => parseFloat(a.flight_hours) - parseFloat(b.flight_hours));

            // Calculate gallons per hour between consecutive records
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

        async deleteNote() {
            if (!this.editingNote) return;
            if (!confirm('Delete this note?')) return;

            this.noteSubmitting = true;
            try {
                const response = await fetch(`/api/aircraft-notes/${this.editingNote.id}/`, {
                    method: 'DELETE',
                    headers: {
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                });

                if (response.ok) {
                    showNotification('Note deleted', 'success');
                    this.closeNoteModal();
                    await this.loadData();
                } else {
                    showNotification('Failed to delete note', 'danger');
                }
            } catch (error) {
                console.error('Error deleting note:', error);
                showNotification('Error deleting note', 'danger');
            } finally {
                this.noteSubmitting = false;
            }
        },

        // AD management methods
        get adIssueCount() {
            return this.applicableAds.filter(
                ad => ad.compliance_status === 'overdue' || ad.compliance_status === 'no_compliance'
            ).length;
        },

        async loadAds() {
            try {
                const response = await fetch(`/api/aircraft/${this.aircraftId}/ads/`);
                const data = await response.json();
                this.applicableAds = data.ads || [];
                this.adsLoaded = true;
            } catch (error) {
                console.error('Error loading ADs:', error);
                showNotification('Failed to load ADs', 'danger');
            }
        },

        async loadAllAds() {
            try {
                const response = await fetch('/api/ad/');
                const data = await response.json();
                const all = data.results || data;
                // Filter out ADs already applicable to this aircraft
                const applicableIds = new Set(this.applicableAds.map(a => a.id));
                this.allAds = all;
                return all;
            } catch (error) {
                console.error('Error loading all ADs:', error);
                return [];
            }
        },

        get availableAds() {
            const applicableIds = new Set(this.applicableAds.map(a => a.id));
            return this.allAds.filter(a => !applicableIds.has(a.id));
        },

        openAdModal() {
            this.editingAd = null;
            this.selectedExistingAdId = '';
            this.adForm = {
                name: '',
                short_description: '',
                required_action: '',
                recurring: false,
                recurring_hours: 0,
                recurring_months: 0,
                recurring_days: 0,
            };
            this.loadAllAds();
            this.adModalOpen = true;
        },

        editAd(ad) {
            this.editingAd = ad;
            this.selectedExistingAdId = '';
            this.adForm = {
                name: ad.name,
                short_description: ad.short_description,
                required_action: ad.required_action || '',
                recurring: ad.recurring,
                recurring_hours: ad.recurring_hours || 0,
                recurring_months: ad.recurring_months || 0,
                recurring_days: ad.recurring_days || 0,
            };
            this.adModalOpen = true;
        },

        closeAdModal() {
            this.adModalOpen = false;
            this.editingAd = null;
        },

        async addExistingAd() {
            if (!this.selectedExistingAdId || this.adSubmitting) return;
            this.adSubmitting = true;
            try {
                const response = await fetch(`/api/aircraft/${this.aircraftId}/ads/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                    body: JSON.stringify({ ad_id: this.selectedExistingAdId }),
                });

                if (response.ok) {
                    showNotification('AD added to aircraft', 'success');
                    this.closeAdModal();
                    this.adsLoaded = false;
                    await this.loadAds();
                    await this.loadData();
                } else {
                    const errorData = await response.json();
                    showNotification(errorData.error || 'Failed to add AD', 'danger');
                }
            } catch (error) {
                console.error('Error adding AD:', error);
                showNotification('Error adding AD', 'danger');
            } finally {
                this.adSubmitting = false;
            }
        },

        async createAndAddAd() {
            if (!this.adForm.name || !this.adForm.short_description || this.adSubmitting) return;
            this.adSubmitting = true;
            try {
                const data = {
                    name: this.adForm.name,
                    short_description: this.adForm.short_description,
                    required_action: this.adForm.required_action,
                    recurring: this.adForm.recurring,
                    recurring_hours: this.adForm.recurring ? parseFloat(this.adForm.recurring_hours) || 0 : 0,
                    recurring_months: this.adForm.recurring ? parseInt(this.adForm.recurring_months) || 0 : 0,
                    recurring_days: this.adForm.recurring ? parseInt(this.adForm.recurring_days) || 0 : 0,
                };

                const response = await fetch(`/api/aircraft/${this.aircraftId}/ads/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                    body: JSON.stringify(data),
                });

                if (response.ok) {
                    showNotification('AD created and added to aircraft', 'success');
                    this.closeAdModal();
                    this.adsLoaded = false;
                    await this.loadAds();
                    await this.loadData();
                } else {
                    const errorData = await response.json();
                    const msg = typeof errorData === 'object'
                        ? Object.values(errorData).flat().join(', ')
                        : 'Failed to create AD';
                    showNotification(msg, 'danger');
                }
            } catch (error) {
                console.error('Error creating AD:', error);
                showNotification('Error creating AD', 'danger');
            } finally {
                this.adSubmitting = false;
            }
        },

        async updateAd() {
            if (!this.adForm.name || !this.adForm.short_description || this.adSubmitting) return;
            this.adSubmitting = true;
            try {
                const data = {
                    name: this.adForm.name,
                    short_description: this.adForm.short_description,
                    required_action: this.adForm.required_action,
                    recurring: this.adForm.recurring,
                    recurring_hours: this.adForm.recurring ? parseFloat(this.adForm.recurring_hours) || 0 : 0,
                    recurring_months: this.adForm.recurring ? parseInt(this.adForm.recurring_months) || 0 : 0,
                    recurring_days: this.adForm.recurring ? parseInt(this.adForm.recurring_days) || 0 : 0,
                };

                const response = await fetch(`/api/ad/${this.editingAd.id}/`, {
                    method: 'PATCH',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                    body: JSON.stringify(data),
                });

                if (response.ok) {
                    showNotification('AD updated', 'success');
                    this.closeAdModal();
                    this.adsLoaded = false;
                    await this.loadAds();
                    await this.loadData();
                } else {
                    const errorData = await response.json();
                    const msg = typeof errorData === 'object'
                        ? Object.values(errorData).flat().join(', ')
                        : 'Failed to update AD';
                    showNotification(msg, 'danger');
                }
            } catch (error) {
                console.error('Error updating AD:', error);
                showNotification('Error updating AD', 'danger');
            } finally {
                this.adSubmitting = false;
            }
        },

        async removeAd(ad) {
            if (!confirm(`Remove AD "${ad.name}" from this aircraft?`)) return;
            try {
                const response = await fetch(`/api/aircraft/${this.aircraftId}/remove_ad/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                    body: JSON.stringify({ ad_id: ad.id }),
                });

                if (response.ok) {
                    showNotification('AD removed from aircraft', 'success');
                    this.adsLoaded = false;
                    await this.loadAds();
                    await this.loadData();
                } else {
                    showNotification('Failed to remove AD', 'danger');
                }
            } catch (error) {
                console.error('Error removing AD:', error);
                showNotification('Error removing AD', 'danger');
            }
        },

        openComplianceModal(ad) {
            this.selectedAd = ad;
            this.complianceForm = {
                date_complied: new Date().toISOString().split('T')[0],
                compliance_notes: '',
                permanent: false,
                next_due_at_time: '',
            };
            // Auto-calculate next due if recurring
            if (ad.recurring && ad.recurring_hours > 0 && this.aircraft) {
                this.complianceForm.next_due_at_time = (
                    parseFloat(this.aircraft.flight_time) + parseFloat(ad.recurring_hours)
                ).toFixed(1);
            }
            this.complianceModalOpen = true;
        },

        closeComplianceModal() {
            this.complianceModalOpen = false;
            this.selectedAd = null;
        },

        async submitCompliance() {
            if (this.complianceSubmitting || !this.selectedAd) return;
            this.complianceSubmitting = true;
            try {
                const data = {
                    ad: this.selectedAd.id,
                    date_complied: this.complianceForm.date_complied,
                    compliance_notes: this.complianceForm.compliance_notes,
                    permanent: this.complianceForm.permanent,
                    next_due_at_time: this.complianceForm.permanent ? 0 : (parseFloat(this.complianceForm.next_due_at_time) || 0),
                };

                const response = await fetch(`/api/aircraft/${this.aircraftId}/compliance/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                    body: JSON.stringify(data),
                });

                if (response.ok) {
                    showNotification('Compliance recorded', 'success');
                    this.closeComplianceModal();
                    this.adsLoaded = false;
                    await this.loadAds();
                    await this.loadData();
                } else {
                    const errorData = await response.json();
                    const msg = typeof errorData === 'object'
                        ? Object.values(errorData).flat().join(', ')
                        : 'Failed to record compliance';
                    showNotification(msg, 'danger');
                }
            } catch (error) {
                console.error('Error recording compliance:', error);
                showNotification('Error recording compliance', 'danger');
            } finally {
                this.complianceSubmitting = false;
            }
        },

        getAdStatusClass(ad) {
            switch (ad.compliance_status) {
                case 'compliant':
                    return 'pf-m-green';
                case 'due_soon':
                    return 'pf-m-orange';
                case 'overdue':
                    return 'pf-m-red';
                case 'no_compliance':
                    return 'pf-m-red';
                default:
                    return 'pf-m-grey';
            }
        },

        getAdStatusText(ad) {
            switch (ad.compliance_status) {
                case 'compliant':
                    return 'Compliant';
                case 'due_soon':
                    return 'Due Soon';
                case 'overdue':
                    return 'Overdue';
                case 'no_compliance':
                    return 'No Compliance';
                default:
                    return 'Unknown';
            }
        },

        // Collection CRUD methods
        openCollectionModal() {
            this.editingCollection = null;
            this.collectionForm = { name: '', description: '' };
            this.collectionModalOpen = true;
        },

        editCollection(collection) {
            this.editingCollection = collection;
            this.collectionForm = {
                name: collection.name,
                description: collection.description || '',
            };
            this.collectionModalOpen = true;
        },

        closeCollectionModal() {
            this.collectionModalOpen = false;
            this.editingCollection = null;
        },

        async submitCollection() {
            if (this.collectionSubmitting) return;
            if (!this.collectionForm.name.trim()) {
                showNotification('Collection name is required', 'warning');
                return;
            }

            this.collectionSubmitting = true;
            try {
                const data = {
                    name: this.collectionForm.name,
                    description: this.collectionForm.description,
                };

                let response;
                if (this.editingCollection) {
                    response = await fetch(`/api/document-collection/${this.editingCollection.id}/`, {
                        method: 'PATCH',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': getCookie('csrftoken'),
                        },
                        body: JSON.stringify(data),
                    });
                } else {
                    data.aircraft = `/api/aircraft/${this.aircraftId}/`;
                    data.components = [];
                    response = await fetch('/api/document-collection/', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': getCookie('csrftoken'),
                        },
                        body: JSON.stringify(data),
                    });
                }

                if (response.ok) {
                    showNotification(
                        this.editingCollection ? 'Collection updated' : 'Collection created',
                        'success'
                    );
                    this.closeCollectionModal();
                    this.documentsLoaded = false;
                    await this.loadDocuments();
                } else {
                    const errorData = await response.json();
                    const msg = typeof errorData === 'object'
                        ? Object.values(errorData).flat().join(', ')
                        : 'Failed to save collection';
                    showNotification(msg, 'danger');
                }
            } catch (error) {
                console.error('Error saving collection:', error);
                showNotification('Error saving collection', 'danger');
            } finally {
                this.collectionSubmitting = false;
            }
        },

        async deleteCollection(collection) {
            if (!confirm(`Delete collection "${collection.name}"?\n\nAll documents in this collection will also be deleted. This cannot be undone.`)) {
                return;
            }

            try {
                const response = await fetch(`/api/document-collection/${collection.id}/`, {
                    method: 'DELETE',
                    headers: {
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                });

                if (response.ok || response.status === 204) {
                    showNotification('Collection deleted', 'success');
                    this.documentsLoaded = false;
                    await this.loadDocuments();
                } else {
                    showNotification('Failed to delete collection', 'danger');
                }
            } catch (error) {
                console.error('Error deleting collection:', error);
                showNotification('Error deleting collection', 'danger');
            }
        },

        // Document CRUD methods
        openDocumentModal() {
            this.editingDocument = null;
            this.documentForm = {
                name: '',
                description: '',
                doc_type: 'OTHER',
                collection: '',
            };
            this.documentImageFiles = [];
            this.documentModalOpen = true;
        },

        editDocument(doc, event) {
            if (event) event.stopPropagation();
            this.editingDocument = doc;
            this.documentForm = {
                name: doc.name,
                description: doc.description || '',
                doc_type: doc.doc_type,
                collection: doc.collection_id || '',
            };
            this.documentImageFiles = [];
            this.documentModalOpen = true;
        },

        closeDocumentModal() {
            this.documentModalOpen = false;
            this.editingDocument = null;
            this.documentImageFiles = [];
        },

        onDocumentFilesSelected(event) {
            this.documentImageFiles = Array.from(event.target.files);
        },

        async submitDocument() {
            if (this.documentSubmitting) return;
            if (!this.documentForm.name.trim()) {
                showNotification('Document name is required', 'warning');
                return;
            }

            this.documentSubmitting = true;
            try {
                const data = {
                    name: this.documentForm.name,
                    description: this.documentForm.description,
                    doc_type: this.documentForm.doc_type,
                };

                let response;
                if (this.editingDocument) {
                    if (this.documentForm.collection) {
                        data.collection = `/api/document-collection/${this.documentForm.collection}/`;
                    } else {
                        data.collection = null;
                    }
                    response = await fetch(`/api/document/${this.editingDocument.id}/`, {
                        method: 'PATCH',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': getCookie('csrftoken'),
                        },
                        body: JSON.stringify(data),
                    });
                } else {
                    data.aircraft = `/api/aircraft/${this.aircraftId}/`;
                    if (this.documentForm.collection) {
                        data.collection = `/api/document-collection/${this.documentForm.collection}/`;
                    } else {
                        data.collection = null;
                    }
                    data.components = [];
                    response = await fetch('/api/document/', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': getCookie('csrftoken'),
                        },
                        body: JSON.stringify(data),
                    });
                }

                if (response.ok) {
                    const docData = await response.json();
                    const docId = docData.id;

                    // Upload images
                    let uploadFailed = false;
                    for (const file of this.documentImageFiles) {
                        const formData = new FormData();
                        formData.append('document', `/api/document/${docId}/`);
                        formData.append('image', file);
                        formData.append('notes', '');
                        const imgResponse = await fetch('/api/document-image/', {
                            method: 'POST',
                            headers: {
                                'X-CSRFToken': getCookie('csrftoken'),
                            },
                            body: formData,
                        });
                        if (!imgResponse.ok) {
                            console.error('Image upload failed:', await imgResponse.text());
                            uploadFailed = true;
                        }
                    }
                    if (uploadFailed) {
                        showNotification('Document saved but some images failed to upload', 'warning');
                    }

                    showNotification(
                        this.editingDocument ? 'Document updated' : 'Document created',
                        'success'
                    );
                    this.closeDocumentModal();
                    this.documentsLoaded = false;
                    await this.loadDocuments();
                } else {
                    const errorData = await response.json();
                    const msg = typeof errorData === 'object'
                        ? Object.values(errorData).flat().join(', ')
                        : 'Failed to save document';
                    showNotification(msg, 'danger');
                }
            } catch (error) {
                console.error('Error saving document:', error);
                showNotification('Error saving document', 'danger');
            } finally {
                this.documentSubmitting = false;
            }
        },

        async deleteDocument(doc, event) {
            if (event) event.stopPropagation();
            if (!confirm(`Delete document "${doc.name}"?\n\nThis action cannot be undone.`)) {
                return;
            }

            try {
                const response = await fetch(`/api/document/${doc.id}/`, {
                    method: 'DELETE',
                    headers: {
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                });

                if (response.ok || response.status === 204) {
                    showNotification('Document deleted', 'success');
                    this.documentsLoaded = false;
                    await this.loadDocuments();
                } else {
                    showNotification('Failed to delete document', 'danger');
                }
            } catch (error) {
                console.error('Error deleting document:', error);
                showNotification('Error deleting document', 'danger');
            }
        },

        async deleteDocumentImage(imageId) {
            if (!confirm('Delete this image?')) return;

            try {
                const response = await fetch(`/api/document-image/${imageId}/`, {
                    method: 'DELETE',
                    headers: {
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                });

                if (response.ok || response.status === 204) {
                    showNotification('Image deleted', 'success');
                    // Remove from editing document's images
                    if (this.editingDocument?.images) {
                        this.editingDocument.images = this.editingDocument.images.filter(img => img.id !== imageId);
                    }
                    this.documentsLoaded = false;
                    await this.loadDocuments();
                } else {
                    showNotification('Failed to delete image', 'danger');
                }
            } catch (error) {
                console.error('Error deleting image:', error);
                showNotification('Error deleting image', 'danger');
            }
        },

        // Aircraft edit/delete methods
        openEditModal() {
            window.dispatchEvent(new CustomEvent('open-aircraft-modal', {
                detail: { aircraft: this.aircraft }
            }));
        },

        openDeleteModal() {
            window.dispatchEvent(new CustomEvent('open-aircraft-delete-modal', {
                detail: { aircraft: this.aircraft }
            }));
        },
    }
}
