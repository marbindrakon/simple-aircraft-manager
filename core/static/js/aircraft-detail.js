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

            // Watch for tab changes to load documents lazily
            this.$watch('activeTab', (tab) => {
                if (tab === 'documents' && !this.documentsLoaded) {
                    this.loadDocuments();
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
            if (component.replacement_critical && component.replacement_hours) {
                interval = component.replacement_hours;
            } else if (component.tbo_hours) {
                interval = component.tbo_hours;
            }

            if (!interval) {
                return 'N/A';
            }

            const remaining = interval - (component.hours_since_overhaul || 0);
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
        }
    }
}
