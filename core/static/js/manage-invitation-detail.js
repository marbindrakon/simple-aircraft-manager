function manageInvitationDetail(invitationId) {
    return {
        code: null,
        loading: true,

        editForm: {},
        saving: false,

        aircraftList: [],
        newRoleAircraftId: '',
        newRoleRole: 'pilot',
        addingRole: false,

        async init() {
            await Promise.all([this.loadCode(), this.loadAircraft()]);
        },

        async loadCode() {
            const { ok, data } = await apiRequest(`/api/invitation-codes/${invitationId}/`);
            if (ok) {
                this.code = data;
                this.editForm = {
                    label: data.label,
                    invited_email: data.invited_email || '',
                    invited_name: data.invited_name || '',
                    max_uses: data.max_uses != null ? String(data.max_uses) : '',
                    expires_at: data.expires_at ? data.expires_at.slice(0, 16) : '',
                    is_active: data.is_active,
                };
            } else {
                showNotification('Failed to load invitation code', 'danger');
            }
            this.loading = false;
        },

        async loadAircraft() {
            const { ok, data } = await apiRequest('/api/aircraft/');
            if (ok) {
                this.aircraftList = Array.isArray(data) ? data : (data.results || []);
            }
        },

        async saveCode() {
            if (!this.editForm.label || !this.editForm.label.trim()) return;
            this.saving = true;
            const body = {
                label: this.editForm.label.trim(),
                invited_email: this.editForm.invited_email || '',
                invited_name: this.editForm.invited_name || '',
                is_active: this.editForm.is_active,
                max_uses: this.editForm.max_uses !== '' ? parseInt(this.editForm.max_uses, 10) : null,
                expires_at: this.editForm.expires_at || null,
            };
            const { ok, data } = await apiRequest(`/api/invitation-codes/${invitationId}/`, {
                method: 'PATCH',
                body: JSON.stringify(body),
            });
            if (ok) {
                this.code = { ...this.code, ...data };
                showNotification('Changes saved', 'success');
            } else {
                showNotification('Failed to save: ' + formatApiError(data), 'danger');
            }
            this.saving = false;
        },

        async addRole() {
            if (!this.newRoleAircraftId) return;
            this.addingRole = true;
            const { ok, data } = await apiRequest('/api/invitation-code-roles/', {
                method: 'POST',
                body: JSON.stringify({
                    invitation_code: invitationId,
                    aircraft: this.newRoleAircraftId,
                    role: this.newRoleRole,
                }),
            });
            if (ok) {
                this.newRoleAircraftId = '';
                showNotification('Aircraft role added', 'success');
                await this.loadCode();
            } else {
                showNotification('Failed to add role: ' + formatApiError(data), 'danger');
            }
            this.addingRole = false;
        },

        async removeRole(roleId) {
            const { ok } = await apiRequest(`/api/invitation-code-roles/${roleId}/`, { method: 'DELETE' });
            if (ok) {
                showNotification('Role removed', 'success');
                await this.loadCode();
            } else {
                showNotification('Failed to remove role', 'danger');
            }
        },

        async copyLink() {
            if (!this.code?.registration_url) return;
            try {
                await navigator.clipboard.writeText(this.code.registration_url);
                showNotification('Registration link copied to clipboard', 'success');
            } catch {
                showNotification('Failed to copy link', 'danger');
            }
        },

        getStatusBadge() {
            if (!this.code) return { text: '', class: '' };
            if (!this.code.is_active) return { text: 'Inactive', class: '' };
            if (!this.code.is_valid) return { text: 'Expired/Exhausted', class: 'pf-m-red' };
            return { text: 'Active', class: 'pf-m-green' };
        },
    };
}
