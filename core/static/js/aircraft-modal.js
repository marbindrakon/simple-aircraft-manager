function aircraftModal() {
    return {
        modalOpen: false,
        deleteModalOpen: false,
        editingAircraft: null,
        submitting: false,
        deleting: false,
        deleteConfirmation: '',
        aircraftForm: {
            tail_number: '',
            make: '',
            model: '',
            serial_number: '',
            description: '',
            purchased: '',
            status: 'AVAILABLE',
            tach_reading: 0,
            tach_time_offset: 0,
            hobbs_reading: 0,
            hobbs_time_offset: 0,
        },
        pictureFile: null,
        removePicture: false,

        init() {
            // Listen for open-aircraft-modal event
            window.addEventListener('open-aircraft-modal', (event) => {
                if (event.detail?.aircraft) {
                    this.openEditModal(event.detail.aircraft);
                } else {
                    this.openCreateModal();
                }
            });

            // Listen for open-aircraft-delete-modal event
            window.addEventListener('open-aircraft-delete-modal', (event) => {
                if (event.detail?.aircraft) {
                    this.openDeleteModal(event.detail.aircraft);
                }
            });
        },

        openCreateModal() {
            this.editingAircraft = null;
            this.aircraftForm = {
                tail_number: '',
                make: '',
                model: '',
                serial_number: '',
                description: '',
                purchased: '',
                status: 'AVAILABLE',
                tach_reading: 0,
                tach_time_offset: 0,
                hobbs_reading: 0,
                hobbs_time_offset: 0,
            };
            this.pictureFile = null;
            this.removePicture = false;
            this.modalOpen = true;
        },

        openEditModal(aircraft) {
            this.editingAircraft = aircraft;
            this.aircraftForm = {
                tail_number: aircraft.tail_number || '',
                make: aircraft.make || '',
                model: aircraft.model || '',
                serial_number: aircraft.serial_number || '',
                description: aircraft.description || '',
                purchased: aircraft.purchased || '',
                status: aircraft.status || 'AVAILABLE',
                tach_reading: (parseFloat(aircraft.tach_time) || 0) - (parseFloat(aircraft.tach_time_offset) || 0),
                tach_time_offset: aircraft.tach_time_offset || 0,
                hobbs_reading: (parseFloat(aircraft.hobbs_time) || 0) - (parseFloat(aircraft.hobbs_time_offset) || 0),
                hobbs_time_offset: aircraft.hobbs_time_offset || 0,
            };
            this.pictureFile = null;
            this.removePicture = false;
            this.modalOpen = true;
        },

        closeModal() {
            this.modalOpen = false;
            this.editingAircraft = null;
            this.pictureFile = null;
            this.removePicture = false;
        },

        handlePictureChange(event) {
            const file = event.target.files[0];
            if (file) {
                // Validate file type
                const validTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif'];
                if (!validTypes.includes(file.type)) {
                    showNotification('Please select a valid image file (JPEG, PNG, GIF)', 'warning');
                    event.target.value = '';
                    return;
                }
                // Validate file size (max 15MB)
                if (file.size > 15 * 1024 * 1024) {
                    showNotification('Image file must be less than 15MB', 'warning');
                    event.target.value = '';
                    return;
                }
                this.pictureFile = file;
            }
        },

        async submitAircraft() {
            if (this.submitting) return;

            // Basic validation
            if (!this.aircraftForm.tail_number.trim()) {
                showNotification('Tail number is required', 'warning');
                return;
            }

            this.submitting = true;
            try {
                const formData = new FormData();
                formData.append('tail_number', this.aircraftForm.tail_number);
                formData.append('make', this.aircraftForm.make);
                formData.append('model', this.aircraftForm.model);
                formData.append('serial_number', this.aircraftForm.serial_number);
                formData.append('description', this.aircraftForm.description);
                formData.append('status', this.aircraftForm.status);
                const tachOffset = parseFloat(this.aircraftForm.tach_time_offset) || 0;
                const hobbsOffset = parseFloat(this.aircraftForm.hobbs_time_offset) || 0;
                formData.append('tach_time', (parseFloat(this.aircraftForm.tach_reading) || 0) + tachOffset);
                formData.append('tach_time_offset', tachOffset);
                formData.append('hobbs_time', (parseFloat(this.aircraftForm.hobbs_reading) || 0) + hobbsOffset);
                formData.append('hobbs_time_offset', hobbsOffset);

                if (this.aircraftForm.purchased) {
                    formData.append('purchased', this.aircraftForm.purchased);
                }

                if (this.pictureFile) {
                    formData.append('picture', this.pictureFile);
                } else if (this.removePicture && this.editingAircraft) {
                    // Send empty string to clear the picture
                    formData.append('picture', '');
                }

                let response;
                if (this.editingAircraft) {
                    // Update existing aircraft
                    response = await fetch(`/api/aircraft/${this.editingAircraft.id}/`, {
                        method: 'PATCH',
                        headers: {
                            'X-CSRFToken': getCookie('csrftoken'),
                        },
                        body: formData,
                    });
                } else {
                    // Create new aircraft
                    response = await fetch('/api/aircraft/', {
                        method: 'POST',
                        headers: {
                            'X-CSRFToken': getCookie('csrftoken'),
                        },
                        body: formData,
                    });
                }

                if (response.ok) {
                    const data = await response.json();
                    showNotification(
                        this.editingAircraft ? 'Aircraft updated successfully' : 'Aircraft created successfully',
                        'success'
                    );
                    this.closeModal();

                    // Trigger aircraft-updated event to refresh the list
                    window.dispatchEvent(new CustomEvent('aircraft-updated', { detail: { aircraft: data } }));

                    // If editing, reload the page to show updated data
                    if (this.editingAircraft) {
                        setTimeout(() => window.location.reload(), 500);
                    }
                } else {
                    const errorData = await response.json();
                    showNotification(formatApiError(errorData, 'Failed to save aircraft'), 'danger');
                }
            } catch (error) {
                console.error('Error saving aircraft:', error);
                showNotification('Error saving aircraft', 'danger');
            } finally {
                this.submitting = false;
            }
        },

        openDeleteModal(aircraft) {
            this.editingAircraft = aircraft;
            this.deleteConfirmation = '';
            this.deleteModalOpen = true;
        },

        closeDeleteModal() {
            this.deleteModalOpen = false;
            this.editingAircraft = null;
            this.deleteConfirmation = '';
        },

        async deleteAircraft() {
            if (this.deleting) return;

            // Validate confirmation
            if (this.deleteConfirmation !== this.editingAircraft.tail_number) {
                showNotification('Tail number does not match', 'warning');
                return;
            }

            this.deleting = true;
            try {
                const response = await fetch(`/api/aircraft/${this.editingAircraft.id}/`, {
                    method: 'DELETE',
                    headers: {
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                });

                if (response.ok || response.status === 204) {
                    showNotification(`Aircraft ${this.editingAircraft.tail_number} deleted successfully`, 'success');
                    this.closeDeleteModal();

                    // Redirect to dashboard if we're on the detail page
                    if (window.location.pathname.includes('/aircraft/')) {
                        setTimeout(() => window.location.href = '/', 500);
                    } else {
                        // Trigger aircraft-updated event to refresh the list
                        window.dispatchEvent(new CustomEvent('aircraft-updated'));
                    }
                } else {
                    const errorData = await response.json();
                    showNotification(errorData.detail || 'Failed to delete aircraft', 'danger');
                }
            } catch (error) {
                console.error('Error deleting aircraft:', error);
                showNotification('Error deleting aircraft', 'danger');
            } finally {
                this.deleting = false;
            }
        },
    }
}
