function notesMixin() {
    return {
        // Notes state
        aircraftNotes: [],
        showAllNotes: false,
        noteModalOpen: false,
        editingNote: null,
        noteSubmitting: false,
        noteForm: {
            text: '',
        },

        openNoteModal() {
            this.editingNote = null;
            this.noteForm = { text: '' };
            this.noteModalOpen = true;
        },

        viewNote(note) {
            this.editingNote = note;
            this.noteForm = { text: note.text };
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
                    response = await fetch(`/api/aircraft-notes/${this.editingNote.id}/`, {
                        method: 'PATCH',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': getCookie('csrftoken'),
                        },
                        body: JSON.stringify(data),
                    });
                } else {
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
        },
    };
}
