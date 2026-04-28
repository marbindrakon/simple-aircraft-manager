// Toggle the credentials fieldset visibility based on the auth-mode radio.
// CSP requires this to live in an external file rather than inline.
(function () {
    const form = document.getElementById('setup-form');
    if (!form) return;

    const credsFieldset = document.getElementById('creds-fieldset');
    const radios = form.querySelectorAll('input[name="auth_mode"]');

    function syncCredsVisibility() {
        const required = form.querySelector('input[name="auth_mode"]:checked')?.value === 'required';
        credsFieldset.style.display = required ? '' : 'none';
        // Don't enforce HTML5 required attrs when the fieldset is hidden so
        // submitting "no login" mode doesn't get blocked by the browser.
        credsFieldset.querySelectorAll('input').forEach((el) => {
            el.disabled = !required;
        });
    }

    radios.forEach((r) => r.addEventListener('change', syncCredsVisibility));
    syncCredsVisibility();
})();
