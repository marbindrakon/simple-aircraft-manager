function documentsMixin() {
    return {
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
        openDocumentViewer(doc, collectionName, startPage) {
            this.viewerDocument = doc;
            this.viewerCollectionName = collectionName;
            this.viewerImageIndex = startPage || 0;
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
                    response = await fetch(`/api/document-collections/${this.editingCollection.id}/`, {
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
                    response = await fetch('/api/document-collections/', {
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
                const response = await fetch(`/api/document-collections/${collection.id}/`, {
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

        openDocumentModalForCollection(collection) {
            this.editingDocument = null;
            this.documentForm = {
                name: '',
                description: '',
                doc_type: 'OTHER',
                collection: collection.id,
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
                        data.collection = `/api/document-collections/${this.documentForm.collection}/`;
                    } else {
                        data.collection = null;
                    }
                    response = await fetch(`/api/documents/${this.editingDocument.id}/`, {
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
                        data.collection = `/api/document-collections/${this.documentForm.collection}/`;
                    } else {
                        data.collection = null;
                    }
                    data.components = [];
                    response = await fetch('/api/documents/', {
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

                    let uploadFailed = false;
                    for (const file of this.documentImageFiles) {
                        const formData = new FormData();
                        formData.append('document', `/api/documents/${docId}/`);
                        formData.append('image', file);
                        formData.append('notes', '');
                        const imgResponse = await fetch('/api/document-images/', {
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
                const response = await fetch(`/api/documents/${doc.id}/`, {
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

        async setCollectionVisibility(collection, value) {
            // value: 'private' | 'status' | 'maintenance'
            try {
                await apiRequest(`/api/document-collections/${collection.id}/`, { method: 'PATCH', body: JSON.stringify({ visibility: value }) });
                collection.visibility = value;
                const labels = {
                    private: 'Private',
                    status: 'Visible to all share links',
                    maintenance: 'Maintenance links only',
                };
                showNotification(`Collection: ${labels[value]}`, 'success');
            } catch (error) {
                console.error('Error updating collection visibility:', error);
                showNotification('Failed to update collection visibility', 'danger');
            }
        },

        async toggleDocumentSharing(doc) {
            // For docs in a collection: null (inherit) → status → maintenance → private → null
            // For uncollected docs (no collection_id): status → maintenance → private → status
            const hasCollection = !!doc.collection_id;
            let newValue;
            if (doc.visibility === null || doc.visibility === undefined) {
                newValue = 'status';
            } else if (doc.visibility === 'status') {
                newValue = 'maintenance';
            } else if (doc.visibility === 'maintenance') {
                newValue = 'private';
            } else {
                // 'private'
                newValue = hasCollection ? null : 'status';
            }

            try {
                await apiRequest(`/api/documents/${doc.id}/`, { method: 'PATCH', body: JSON.stringify({ visibility: newValue }) });
                doc.visibility = newValue;
                const labels = {
                    status: 'Visible to all share links',
                    maintenance: 'Maintenance links only',
                    private: 'Hidden',
                };
                const label = newValue === null ? 'Inherits from collection' : labels[newValue];
                showNotification(`Document: ${label}`, 'success');
            } catch (error) {
                console.error('Error toggling document visibility:', error);
                showNotification('Failed to update document visibility', 'danger');
            }
        },

        async deleteDocumentImage(imageId) {
            if (!confirm('Delete this image?')) return;

            try {
                const response = await fetch(`/api/document-images/${imageId}/`, {
                    method: 'DELETE',
                    headers: {
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                });

                if (response.ok || response.status === 204) {
                    showNotification('Image deleted', 'success');
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
    };
}
