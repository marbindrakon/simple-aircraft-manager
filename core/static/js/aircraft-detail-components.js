function componentsMixin() {
    return {
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

        getComponentTypeName(component) {
            return component.component_type_name || 'Unknown';
        },

        calculateHoursToTBO(component) {
            if (!component.tbo_hours) return 'N/A';
            const remaining = component.tbo_hours - (component.hours_since_overhaul || 0);
            return remaining > 0 ? remaining.toFixed(1) : '0.0';
        },

        getComponentCurrentHours(component) {
            if (component.replacement_critical) {
                return component.hours_in_service || 0;
            }
            return component.hours_since_overhaul || 0;
        },

        getComponentInterval(component) {
            if (component.replacement_critical && component.replacement_hours) {
                return component.replacement_hours + ' hrs';
            }
            if (component.tbo_hours) {
                return component.tbo_hours + ' hrs';
            }
            return 'N/A';
        },

        calculateHoursRemaining(component) {
            let interval = null;
            let currentHours = 0;

            if (component.replacement_critical && component.replacement_hours) {
                interval = component.replacement_hours;
                currentHours = component.hours_in_service || 0;
            } else if (component.tbo_hours) {
                interval = component.tbo_hours;
                currentHours = component.hours_since_overhaul || 0;
            }

            if (!interval) return 'N/A';
            const remaining = interval - currentHours;
            return remaining > 0 ? remaining.toFixed(1) : '0.0';
        },

        getHoursRemainingClass(component) {
            const remaining = this.calculateHoursRemaining(component);
            if (remaining === 'N/A') return '';
            const hours = parseFloat(remaining);
            if (hours <= 0) return 'hours-overdue';
            if (hours < 10) return 'hours-critical';
            if (hours < 25) return 'hours-warning';
            return '';
        },

        async resetComponentService(component) {
            const typeName = this.getComponentTypeName(component);
            if (!confirm(`Reset service time for ${typeName}?\n\nThis will set hours since service to 0 and update the service date to today.`)) {
                return;
            }

            try {
                const response = await fetch(`/api/components/${component.id}/reset_service/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                });

                if (response.ok) {
                    const data = await response.json();
                    showNotification(`${typeName} service reset - was ${data.old_hours} hrs`, 'success');
                    await this.loadData();
                } else {
                    showNotification('Failed to reset service time', 'danger');
                }
            } catch (error) {
                console.error('Error resetting service:', error);
                showNotification('Error resetting service time', 'danger');
            }
        },

        async loadComponentTypes() {
            if (this.componentTypesLoaded) return;
            try {
                const response = await fetch('/api/component-types/');
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
                    response = await fetch(`/api/components/${this.editingComponent.id}/`, {
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
                const response = await fetch(`/api/components/${component.id}/`, {
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
            const roots = this.components.filter(c => !c.parent_component_id);
            const result = [];

            const addWithChildren = (component) => {
                result.push(component);
                const children = this.components.filter(c => c.parent_component_id === component.id);
                children.forEach(child => addWithChildren(child));
            };

            roots.forEach(root => addWithChildren(root));

            const added = new Set(result.map(c => c.id));
            this.components.forEach(c => {
                if (!added.has(c.id)) result.push(c);
            });

            return result;
        },

        getParentOptions(excludeId) {
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
                const hoursToTBO = this.calculateHoursToTBO(component);
                if (hoursToTBO !== 'N/A') {
                    const hours = parseFloat(hoursToTBO);
                    if (hours <= 0) return 'pf-m-red';
                    if (hours < 50) return 'pf-m-orange';
                }
                return 'pf-m-green';
            } else if (component.status === 'SPARE') {
                return 'pf-m-blue';
            } else if (component.status === 'DISPOSED') {
                return 'pf-m-red';
            }
            return 'pf-m-grey';
        },
    };
}
