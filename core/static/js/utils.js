// CSRF token helper
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Notification helper (using PatternFly alerts)
function showNotification(message, type = 'info') {
    const alertContainer = document.createElement('div');
    alertContainer.style.position = 'fixed';
    alertContainer.style.top = '20px';
    alertContainer.style.right = '20px';
    alertContainer.style.zIndex = '9999';

    const typeClass = type === 'success' ? 'pf-m-success' :
                      type === 'danger' ? 'pf-m-danger' :
                      type === 'warning' ? 'pf-m-warning' : 'pf-m-info';

    const alertHTML = `
        <div class="pf-v5-c-alert ${typeClass}" role="alert">
            <div class="pf-v5-c-alert__icon">
                <i class="fas fa-${type === 'success' ? 'check-circle' :
                                   type === 'danger' ? 'exclamation-circle' :
                                   type === 'warning' ? 'exclamation-triangle' : 'info-circle'}"></i>
            </div>
            <div class="pf-v5-c-alert__description">${message}</div>
        </div>
    `;

    alertContainer.innerHTML = alertHTML;
    document.body.appendChild(alertContainer);

    setTimeout(() => {
        alertContainer.remove();
    }, 3000);
}

// Date formatting
function formatDate(dateString) {
    return new Date(dateString).toLocaleDateString();
}

// Number formatting
function formatHours(hours) {
    return parseFloat(hours || 0).toFixed(1);
}

// Airworthiness status helpers
function getAirworthinessClass(statusStr) {
    switch (statusStr) {
        case 'RED': return 'airworthiness-red';
        case 'ORANGE': return 'airworthiness-orange';
        default: return 'airworthiness-green';
    }
}

function getAirworthinessText(statusStr) {
    switch (statusStr) {
        case 'RED': return 'Grounded';
        case 'ORANGE': return 'Caution';
        default: return 'Airworthy';
    }
}

function getAirworthinessTooltip(airworthiness) {
    if (!airworthiness || airworthiness.status === 'GREEN') {
        return 'Aircraft is airworthy';
    }
    const issues = airworthiness.issues || [];
    if (issues.length === 0) {
        return airworthiness.status === 'RED' ? 'Aircraft is grounded' : 'Maintenance due soon';
    }
    return issues.map(i => `${i.category}: ${i.title}`).join('\n');
}

// Squawk priority badge class
function getSquawkPriorityClass(priority) {
    switch (priority) {
        case 0: return 'pf-m-red';
        case 1: return 'pf-m-orange';
        case 2: return 'pf-m-blue';
        default: return 'pf-m-grey';
    }
}

// Extract a human-readable error message from an API error response body
function formatApiError(errorData, fallback = 'An error occurred') {
    if (typeof errorData === 'object' && errorData !== null) {
        const values = Object.values(errorData).flat();
        if (values.length > 0) return values.join(', ');
    }
    return fallback;
}

// API helper — handles CSRF, JSON serialization, and error parsing.
// Returns { ok, data, status } on success/failure, or { ok: false, error } on network error.
async function apiRequest(url, options = {}) {
    const headers = { ...options.headers };

    if (options.method && options.method !== 'GET') {
        headers['X-CSRFToken'] = getCookie('csrftoken');
    }

    // Only set Content-Type for non-FormData bodies
    if (options.body && !(options.body instanceof FormData)) {
        headers['Content-Type'] = headers['Content-Type'] || 'application/json';
    }

    const mergedOptions = { ...options, headers };

    try {
        const response = await fetch(url, mergedOptions);
        // Handle 204 No Content
        if (response.status === 204) {
            return { ok: true, data: null, status: 204 };
        }
        const data = await response.json();
        return { ok: response.ok, data, status: response.status };
    } catch (error) {
        console.error('API request failed:', error);
        return { ok: false, error: error.message };
    }
}
