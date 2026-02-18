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
        _userSearchTimer: null,

        // Share token management
        shareTokens: [],
        shareTokensLoaded: false,
        shareTokenModalOpen: false,
        shareTokenForm: { label: '', privilege: 'status', expires_in_days: '' },
        shareTokenSubmitting: false,
        shareTokenError: null,

        async loadRoles() {
            const { ok, data } = await apiRequest(`/api/aircraft/${this.aircraftId}/manage_roles/`);
            if (ok) {
                this.roles = data.roles || [];
                this.rolesLoaded = true;
            }
            // Load share tokens alongside roles
            await this.loadShareTokens();
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

        // Share token methods
        async loadShareTokens() {
            const { ok, data } = await apiRequest(`/api/aircraft/${this.aircraftId}/share_tokens/`);
            if (ok) {
                this.shareTokens = Array.isArray(data) ? data : [];
                this.shareTokensLoaded = true;
            }
        },

        openShareTokenModal() {
            this.shareTokenForm = { label: '', privilege: 'status', expires_in_days: '' };
            this.shareTokenError = null;
            this.shareTokenModalOpen = true;
        },

        closeShareTokenModal() {
            this.shareTokenModalOpen = false;
            this.shareTokenError = null;
        },

        async createShareToken() {
            if (this.shareTokenSubmitting) return;
            this.shareTokenSubmitting = true;
            this.shareTokenError = null;

            const payload = {
                privilege: this.shareTokenForm.privilege,
                label: this.shareTokenForm.label.trim(),
            };
            if (this.shareTokenForm.expires_in_days) {
                const days = parseInt(this.shareTokenForm.expires_in_days, 10);
                if (days > 0) payload.expires_in_days = days;
            }

            const { ok, data } = await apiRequest(`/api/aircraft/${this.aircraftId}/share_tokens/`, {
                method: 'POST',
                body: JSON.stringify(payload),
            });
            this.shareTokenSubmitting = false;
            if (ok) {
                this.shareTokens.push(data);
                this.closeShareTokenModal();
                showNotification('Share link created', 'success');
            } else {
                this.shareTokenError = formatApiError(data, 'Failed to create share link');
            }
        },

        async revokeShareToken(tokenId) {
            if (!confirm('Revoke this share link? Anyone with the link will no longer be able to access it.')) return;
            const { ok } = await apiRequest(
                `/api/aircraft/${this.aircraftId}/share_tokens/${tokenId}/`,
                { method: 'DELETE' }
            );
            if (ok) {
                this.shareTokens = this.shareTokens.filter(t => t.id !== tokenId);
                showNotification('Share link revoked', 'success');
            } else {
                showNotification('Failed to revoke share link', 'danger');
            }
        },

        copyTokenUrl(url) {
            navigator.clipboard.writeText(url).then(() => {
                showNotification('Share link copied to clipboard', 'success');
            });
        },
    };
}
