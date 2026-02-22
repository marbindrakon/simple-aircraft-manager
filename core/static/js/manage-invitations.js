function manageInvitations() {
    return {
        codes: [],
        loading: true,

        createModalOpen: false,
        createForm: { label: '', invited_email: '', invited_name: '', max_uses: '', expires_at: '' },
        createSubmitting: false,

        deletingId: null,

        async init() {
            await this.loadCodes();
        },

        async loadCodes() {
            this.loading = true;
            const { ok, data } = await apiRequest('/api/invitation-codes/');
            if (ok) {
                this.codes = Array.isArray(data) ? data : (data.results || []);
            } else {
                showNotification('Failed to load invitation codes', 'danger');
            }
            this.loading = false;
        },

        async createCode() {
            if (!this.createForm.label.trim()) return;
            this.createSubmitting = true;
            const body = { label: this.createForm.label.trim() };
            if (this.createForm.invited_email) body.invited_email = this.createForm.invited_email;
            if (this.createForm.invited_name) body.invited_name = this.createForm.invited_name;
            if (this.createForm.max_uses) body.max_uses = parseInt(this.createForm.max_uses, 10);
            if (this.createForm.expires_at) body.expires_at = this.createForm.expires_at;

            const { ok, data } = await apiRequest('/api/invitation-codes/', {
                method: 'POST',
                body: JSON.stringify(body),
            });
            if (ok) {
                this.createModalOpen = false;
                this.createForm = { label: '', invited_email: '', invited_name: '', max_uses: '', expires_at: '' };
                showNotification('Invitation code created', 'success');
                await this.loadCodes();
            } else {
                showNotification('Failed to create: ' + formatApiError(data), 'danger');
            }
            this.createSubmitting = false;
        },

        async toggleActive(code) {
            const { ok, data } = await apiRequest(`/api/invitation-codes/${code.id}/toggle_active/`, {
                method: 'POST',
            });
            if (ok) {
                const idx = this.codes.findIndex(c => c.id === code.id);
                if (idx !== -1) this.codes[idx] = data;
                showNotification(`Code ${data.is_active ? 'activated' : 'deactivated'}`, 'success');
            } else {
                showNotification('Failed to toggle code', 'danger');
            }
        },

        async deleteCode(id) {
            const { ok } = await apiRequest(`/api/invitation-codes/${id}/`, { method: 'DELETE' });
            this.deletingId = null;
            if (ok) {
                showNotification('Invitation code deleted', 'success');
                await this.loadCodes();
            } else {
                showNotification('Failed to delete code', 'danger');
            }
        },

        async copyLink(url) {
            try {
                await navigator.clipboard.writeText(url);
                showNotification('Registration link copied to clipboard', 'success');
            } catch {
                showNotification('Failed to copy link', 'danger');
            }
        },

        getStatusBadge(code) {
            if (!code.is_active) return { text: 'Inactive', class: '' };
            if (!code.is_valid) return { text: 'Expired/Exhausted', class: 'pf-m-red' };
            return { text: 'Active', class: 'pf-m-green' };
        },

        formatUses(code) {
            const count = code.use_count !== undefined ? code.use_count : 0;
            return code.max_uses != null ? `${count} / ${code.max_uses}` : `${count} / ∞`;
        },
    };
}
