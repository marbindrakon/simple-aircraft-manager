/* Logbook import page Alpine.js component */

function logbookImport() {
    return {
        // ── Form fields ──────────────────────────────────────────────────────
        aircraftId: '',
        collectionName: '',
        docName: '',
        docType: 'LOG',
        model: 'claude-sonnet-4-5-20250929',
        batchSize: 10,
        uploadOnly: false,
        logTypeOverride: '',
        fileMode: 'images',   // 'images' | 'archive'

        // ── UI state ─────────────────────────────────────────────────────────
        importing: false,
        done: false,
        events: [],
        result: null,
        fatalError: null,

        // Selected file info (display only)
        selectedImages: [],
        selectedArchive: null,

        // ── Computed ─────────────────────────────────────────────────────────
        get canSubmit() {
            if (!this.aircraftId || this.importing) return false;
            if (this.fileMode === 'images') return this.selectedImages.length > 0;
            return this.selectedArchive !== null;
        },

        get imageCount() {
            return this.selectedImages.length;
        },

        get batchCount() {
            return this.events.filter(e => e.type === 'batch').length;
        },

        get totalBatches() {
            const last = [...this.events].reverse().find(e => e.type === 'batch');
            return last ? last.total_batches : 0;
        },

        get entryCount() {
            return this.events.filter(e => e.type === 'entry').length;
        },

        get uploadedCount() {
            return this.events.filter(e => e.type === 'image').length;
        },

        get errorCount() {
            return this.events.filter(e => e.type === 'error').length;
        },

        get warningCount() {
            return this.events.filter(e => e.type === 'warning').length;
        },

        get progressPercent() {
            if (this.done) return 100;
            if (!this.importing) return 0;
            // Weight: transcription batches 50%, image uploads 40%, entries 10%
            let pct = 0;
            if (this.totalBatches > 0) {
                pct += (this.batchCount / this.totalBatches) * 50;
            }
            const totalImages = this.uploadOnly ? this.imageCount : this.imageCount;
            if (totalImages > 0) {
                pct += (this.uploadedCount / totalImages) * 40;
            }
            return Math.min(Math.round(pct), 99);
        },

        // ── File input handlers ───────────────────────────────────────────────
        onImagesChange(event) {
            const files = Array.from(event.target.files || []);
            this.selectedImages = files;
            // Auto-fill names from first file's directory hint
            if (files.length > 0 && !this.collectionName) {
                const name = files[0].name.replace(/\.[^.]+$/, '').replace(/[-_\d]+$/, '').trim();
                if (name) {
                    this.collectionName = name;
                    this.docName = name;
                }
            }
        },

        onArchiveChange(event) {
            const file = event.target.files[0] || null;
            this.selectedArchive = file;
            if (file && !this.collectionName) {
                const name = file.name.replace(/\.[^.]+$/, '').trim();
                if (name) {
                    this.collectionName = name;
                    this.docName = name;
                }
            }
        },

        // ── Import ────────────────────────────────────────────────────────────
        async startImport() {
            this.importing = true;
            this.done = false;
            this.events = [];
            this.result = null;
            this.fatalError = null;

            const formData = new FormData();
            formData.append('aircraft', this.aircraftId);
            formData.append('collection_name', this.collectionName);
            formData.append('doc_name', this.docName || this.collectionName);
            formData.append('doc_type', this.docType);
            formData.append('model', this.model);
            formData.append('batch_size', String(this.batchSize));
            formData.append('upload_only', this.uploadOnly ? 'true' : 'false');
            formData.append('log_type_override', this.logTypeOverride);
            formData.append('file_mode', this.fileMode);

            if (this.fileMode === 'images') {
                const input = this.$refs.imageInput;
                for (const file of (input ? input.files : [])) {
                    formData.append('images', file);
                }
            } else {
                const input = this.$refs.archiveInput;
                if (input && input.files[0]) {
                    formData.append('archive', input.files[0]);
                }
            }

            try {
                const response = await fetch('/tools/import-logbook/', {
                    method: 'POST',
                    headers: { 'X-CSRFToken': getCookie('csrftoken') },
                    body: formData,
                });

                if (!response.ok) {
                    const text = await response.text();
                    let msg = `HTTP ${response.status}`;
                    try { msg = JSON.parse(text).message || msg; } catch (_) {}
                    this.fatalError = msg;
                    return;
                }

                // Read the NDJSON stream
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop();           // keep incomplete tail
                    for (const line of lines) {
                        const trimmed = line.trim();
                        if (!trimmed) continue;
                        try {
                            this._handleEvent(JSON.parse(trimmed));
                        } catch (_) {
                            // ignore malformed lines
                        }
                    }
                }
                // Flush any remaining buffer
                if (buffer.trim()) {
                    try { this._handleEvent(JSON.parse(buffer.trim())); } catch (_) {}
                }

            } catch (err) {
                this.fatalError = String(err);
            } finally {
                this.importing = false;
                this.done = true;
                // Scroll log to bottom
                this.$nextTick(() => {
                    const log = this.$refs.eventLog;
                    if (log) log.scrollTop = log.scrollHeight;
                });
            }
        },

        _handleEvent(event) {
            this.events.push(event);
            if (event.type === 'complete') {
                this.result = event;
            }
            // Keep log scrolled to bottom while streaming
            this.$nextTick(() => {
                const log = this.$refs.eventLog;
                if (log) log.scrollTop = log.scrollHeight;
            });
        },

        // ── Helpers ───────────────────────────────────────────────────────────
        reset() {
            this.importing = false;
            this.done = false;
            this.events = [];
            this.result = null;
            this.fatalError = null;
            this.selectedImages = [];
            this.selectedArchive = null;
            if (this.$refs.imageInput) this.$refs.imageInput.value = '';
            if (this.$refs.archiveInput) this.$refs.archiveInput.value = '';
        },

        eventClass(event) {
            return {
                'pf-v5-c-log-viewer__text': true,
                'sam-log-info':    event.type === 'info' || event.type === 'batch',
                'sam-log-warning': event.type === 'warning',
                'sam-log-error':   event.type === 'error',
                'sam-log-entry':   event.type === 'entry',
                'sam-log-image':   event.type === 'image',
                'sam-log-complete': event.type === 'complete',
            };
        },

        eventIcon(event) {
            const icons = {
                info:     'fa-circle-info',
                batch:    'fa-layer-group',
                warning:  'fa-triangle-exclamation',
                error:    'fa-circle-xmark',
                entry:    'fa-book',
                image:    'fa-image',
                complete: 'fa-circle-check',
            };
            return icons[event.type] || 'fa-circle';
        },

        formatHoursLabel(entry) {
            if (!entry.hours) return '';
            return `${entry.hours} hrs`;
        },
    };
}
