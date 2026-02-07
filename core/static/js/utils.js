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
    // Create PatternFly alert and auto-dismiss
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

    // Auto-remove after 3 seconds
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
    return parseFloat(hours).toFixed(1);
}

// API helper
async function apiRequest(url, options = {}) {
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
        }
    };

    if (options.method && options.method !== 'GET') {
        defaultOptions.headers['X-CSRFToken'] = getCookie('csrftoken');
    }

    const mergedOptions = {
        ...defaultOptions,
        ...options,
        headers: {
            ...defaultOptions.headers,
            ...(options.headers || {})
        }
    };

    try {
        const response = await fetch(url, mergedOptions);
        const data = await response.json();
        return { ok: response.ok, data, status: response.status };
    } catch (error) {
        console.error('API request failed:', error);
        return { ok: false, error: error.message };
    }
}
