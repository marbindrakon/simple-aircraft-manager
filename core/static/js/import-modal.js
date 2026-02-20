/* global Alpine, getCookie */

function importModal() {
  return {
    modalOpen: false,

    // File state
    selectedArchive: null,
    uploading: false,
    uploadPercent: 0,

    // Job state
    importing: false,
    done: false,
    failed: false,
    events: [],
    result: null,
    _jobId: null,
    _pollInterval: null,
    _eventOffset: 0,

    // Tail-number conflict
    stagedId: null,
    conflictTailNumber: '',
    altTailNumber: '',

    get canSubmit() {
      return !!(this.selectedArchive || (this.stagedId && this.altTailNumber.trim()))
        && !this.uploading;
    },

    init() {
      window.addEventListener('open-import-modal', () => this.open());
    },

    open() {
      this.modalOpen = true;
    },

    maybeClose() {
      if (this.importing) return;   // don't close during active import
      this.close();
    },

    close() {
      this._stopPolling();
      this.modalOpen = false;
      // Reload dashboard if an import completed so the new aircraft appears
      if (this.done && !this.failed) {
        window.dispatchEvent(new CustomEvent('aircraft-updated'));
      }
      this.$nextTick(() => this.reset());
    },

    reset() {
      this._stopPolling();
      this.selectedArchive = null;
      this.uploading = false;
      this.uploadPercent = 0;
      this.importing = false;
      this.done = false;
      this.failed = false;
      this.events = [];
      this.result = null;
      this._jobId = null;
      this._eventOffset = 0;
      this.stagedId = null;
      this.conflictTailNumber = '';
      this.altTailNumber = '';
      if (this.$refs.archiveInput) {
        this.$refs.archiveInput.value = '';
      }
    },

    onArchiveChange(event) {
      const files = event.target.files;
      this.selectedArchive = files && files.length > 0 ? files[0] : null;
      // Clear any prior conflict state when the user picks a new file
      this.conflictTailNumber = '';
      this.altTailNumber = '';
      this.stagedId = null;
    },

    startImport() {
      if (!this.canSubmit) return;

      this.uploading = true;
      this.uploadPercent = 0;
      this.events = [];
      this._eventOffset = 0;
      this.conflictTailNumber = '';

      const formData = new FormData();

      if (this.stagedId) {
        formData.append('staged_id', this.stagedId);
      } else {
        formData.append('archive', this.selectedArchive);
      }

      if (this.altTailNumber.trim()) {
        formData.append('tail_number', this.altTailNumber.trim());
      }

      const xhr = new XMLHttpRequest();
      xhr.open('POST', '/api/aircraft/import/');
      xhr.setRequestHeader('X-CSRFToken', getCookie('csrftoken'));

      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
          this.uploadPercent = Math.round((e.loaded / e.total) * 100);
        }
      };

      xhr.onload = () => {
        this.uploading = false;
        let data;
        try {
          data = JSON.parse(xhr.responseText);
        } catch (_) {
          this._fail('Server returned an unexpected response.');
          return;
        }

        if (xhr.status === 202) {
          this.importing = true;
          this._startPolling(data.job_id);
        } else if (xhr.status === 409 && data.error === 'tail_number_conflict') {
          this.conflictTailNumber = data.tail_number;
          this.altTailNumber = data.tail_number;
          this.stagedId = data.staged_id;
        } else {
          this._fail(data.error || 'Import failed with an unknown error.');
        }
      };

      xhr.onerror = () => {
        this.uploading = false;
        this._fail('Network error during upload. Please try again.');
      };

      xhr.send(formData);
    },

    _startPolling(jobId) {
      this._jobId = jobId;
      this._pollInterval = setInterval(() => this._poll(), 1500);
    },

    async _poll() {
      try {
        const resp = await fetch(
          `/api/aircraft/import/${this._jobId}/?after=${this._eventOffset}`,
          { credentials: 'same-origin' }
        );
        if (!resp.ok) {
          this._stopPolling();
          this._fail(`Polling failed (HTTP ${resp.status}).`);
          return;
        }
        const data = await resp.json();

        for (const ev of (data.events || [])) {
          this._appendEvent(ev);
        }
        this._eventOffset += (data.events || []).length;

        if (data.status === 'completed') {
          this._stopPolling();
          this.importing = false;
          this.done = true;
          this.result = data.result;
        } else if (data.status === 'failed') {
          this._stopPolling();
          this.importing = false;
          this.done = true;
          this.failed = true;
        }
      } catch (_) {
        // Network blip — keep polling
      }
    },

    _appendEvent(ev) {
      this.events.push(ev);
      this.$nextTick(() => {
        const log = this.$refs.eventLog;
        if (log) log.scrollTop = log.scrollHeight;
      });
    },

    _stopPolling() {
      if (this._pollInterval) {
        clearInterval(this._pollInterval);
        this._pollInterval = null;
      }
    },

    _fail(message) {
      this._stopPolling();
      this.uploading = false;
      this.importing = false;
      this.done = true;
      this.failed = true;
      if (message) {
        this._appendEvent({ type: 'error', message });
      }
    },

    eventIcon(ev) {
      switch (ev.type) {
        case 'error':    return 'fa-circle-xmark';
        case 'warning':  return 'fa-triangle-exclamation';
        case 'complete': return 'fa-circle-check';
        default:         return 'fa-circle-dot';
      }
    },
  };
}
