function rolesMixin() {
    return {
        roles: [],
        rolesLoaded: false,
        roleModalOpen: false,
        roleForm: { user: '', role: 'pilot' },
        roleSubmitting: false,
        roleError: null,
        userSearchQuery: '',
        userSearchResults: [],
        userSearchLoading: false,
        selectedUser: null,
        sharingEnabled: false,
        shareUrl: null,
        shareToken: null,
        shareTokenExpiresAt: null,
        sharingSubmitting: false,
        sharingExpiresInDays: '',
        _userSearchTimer: null,

        async loadRoles() {
            const { ok, data } = await apiRequest(`/api/aircraft/${this.aircraftId}/manage_roles/`);
            if (ok) {
                this.roles = data.roles || [];
                this.rolesLoaded = true;
            }
        },

        openRoleModal() {
            this.roleForm = { user: '', role: 'pilot' };
            this.roleError = null;
            this.userSearchQuery = '';
            this.userSearchResults = [];
            this.selectedUser = null;
            this.roleModalOpen = true;
        },

        closeRoleModal() {
            this.roleModalOpen = false;
            this.roleError = null;
            this.userSearchQuery = '';
            this.userSearchResults = [];
            this.selectedUser = null;
        },

        onUserSearchInput() {
            this.selectedUser = null;
            this.roleForm.user = '';
            clearTimeout(this._userSearchTimer);
            if (this.userSearchQuery.length < 2) {
                this.userSearchResults = [];
                return;
            }
            this._userSearchTimer = setTimeout(() => this._doUserSearch(), 300);
        },

        async _doUserSearch() {
            this.userSearchLoading = true;
            const q = encodeURIComponent(this.userSearchQuery);
            const { ok, data } = await apiRequest(`/api/user-search/?q=${q}`);
            this.userSearchLoading = false;
            if (ok) {
                this.userSearchResults = data;
            }
        },

        selectUser(user) {
            this.selectedUser = user;
            this.roleForm.user = user.id;
            this.userSearchQuery = user.display;
            this.userSearchResults = [];
        },

        clearUserSelection() {
            this.selectedUser = null;
            this.roleForm.user = '';
            this.userSearchQuery = '';
            this.userSearchResults = [];
        },

        async addRole() {
            this.roleSubmitting = true;
            this.roleError = null;
            const { ok, data } = await apiRequest(`/api/aircraft/${this.aircraftId}/manage_roles/`, {
                method: 'POST',
                body: JSON.stringify({
                    user: this.roleForm.user,
                    role: this.roleForm.role,
                }),
            });
            this.roleSubmitting = false;
            if (ok) {
                this.roles = data.roles || [];
                this.closeRoleModal();
                showNotification('Role added successfully', 'success');
            } else {
                this.roleError = formatApiError(data, 'Failed to add role');
            }
        },

        async updateRole(roleEntry, newRole) {
            const { ok, data } = await apiRequest(`/api/aircraft/${this.aircraftId}/manage_roles/`, {
                method: 'POST',
                body: JSON.stringify({
                    user: roleEntry.user,
                    role: newRole,
                }),
            });
            if (ok) {
                this.roles = data.roles || [];
                showNotification('Role updated', 'success');
            } else {
                showNotification(formatApiError(data, 'Failed to update role'), 'danger');
            }
        },

        async removeRole(roleEntry) {
            if (!confirm(`Remove ${roleEntry.username || 'this user'} from this aircraft?`)) return;
            const { ok, data } = await apiRequest(`/api/aircraft/${this.aircraftId}/manage_roles/`, {
                method: 'DELETE',
                body: JSON.stringify({ user: roleEntry.user }),
            });
            if (ok) {
                this.roles = data.roles || [];
                showNotification('Role removed', 'success');
            } else {
                showNotification(formatApiError(data, 'Failed to remove role'), 'danger');
            }
        },

        async toggleSharing() {
            this.sharingSubmitting = true;
            const payload = {};
            if (!this.sharingEnabled && this.sharingExpiresInDays) {
                const days = parseInt(this.sharingExpiresInDays, 10);
                if (days > 0) payload.expires_in_days = days;
            }
            const { ok, data } = await apiRequest(`/api/aircraft/${this.aircraftId}/toggle_sharing/`, {
                method: 'POST',
                body: JSON.stringify(payload),
            });
            this.sharingSubmitting = false;
            if (ok) {
                this.sharingEnabled = data.public_sharing_enabled;
                this.shareToken = data.share_token;
                this.shareUrl = data.share_url;
                this.shareTokenExpiresAt = data.share_token_expires_at;
                showNotification(
                    this.sharingEnabled ? 'Public sharing enabled' : 'Public sharing disabled',
                    'success'
                );
            } else {
                showNotification(formatApiError(data, 'Failed to toggle sharing'), 'danger');
            }
        },

        async regenerateToken() {
            if (!confirm('Regenerate share link? The old link will stop working.')) return;
            this.sharingSubmitting = true;
            const { ok, data } = await apiRequest(`/api/aircraft/${this.aircraftId}/regenerate_share_token/`, {
                method: 'POST',
                body: JSON.stringify({}),
            });
            this.sharingSubmitting = false;
            if (ok) {
                this.shareToken = data.share_token;
                this.shareUrl = data.share_url;
                this.shareTokenExpiresAt = data.share_token_expires_at;
                showNotification('Share link regenerated', 'success');
            } else {
                showNotification(formatApiError(data, 'Failed to regenerate token'), 'danger');
            }
        },

        copyShareUrl() {
            if (this.shareUrl) {
                navigator.clipboard.writeText(this.shareUrl).then(() => {
                    showNotification('Share link copied to clipboard', 'success');
                });
            }
        },

        initSharingState() {
            if (this.aircraft) {
                this.sharingEnabled = this.aircraft.public_sharing_enabled || false;
                this.shareToken = this.aircraft.share_token || null;
                this.shareUrl = this.aircraft.share_url || null;
            }
        },
    };
}
