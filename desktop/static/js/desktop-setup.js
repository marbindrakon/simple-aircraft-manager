// Toggle the credentials fieldset visibility based on the auth-mode radio,
// gate the per-provider follow-up inputs on whether the parent provider is
// filled in, and enable only the default-provider radios that correspond
// to a configured provider. CSP requires this to live in an external file
// rather than inline.
(function () {
    const form = document.getElementById('setup-form');
    if (!form) return;

    // -- Auth mode -----------------------------------------------------------

    const credsFieldset = document.getElementById('creds-fieldset');
    const authRadios = form.querySelectorAll('input[name="auth_mode"]');

    function syncCredsVisibility() {
        const required = form.querySelector('input[name="auth_mode"]:checked')?.value === 'required';
        credsFieldset.style.display = required ? '' : 'none';
        // Don't enforce HTML5 required attrs when the fieldset is hidden so
        // submitting "no login" mode doesn't get blocked by the browser.
        credsFieldset.querySelectorAll('input').forEach((el) => {
            el.disabled = !required;
        });
    }

    authRadios.forEach((r) => r.addEventListener('change', syncCredsVisibility));
    syncCredsVisibility();

    // -- AI provider gating --------------------------------------------------

    const anthropicKeyInput = document.getElementById('setup-api-key');
    const ollamaModelInput = document.getElementById('setup-ollama-model');
    const ollamaBaseUrlGroup = document.getElementById('ollama-base-url-group');
    const ollamaBaseUrlInput = document.getElementById('setup-ollama-base-url');
    const litellmModelInput = document.getElementById('setup-litellm-model');
    const litellmBaseUrlGroup = document.getElementById('litellm-base-url-group');
    const litellmBaseUrlInput = document.getElementById('setup-litellm-base-url');
    const litellmApiKeyGroup = document.getElementById('litellm-api-key-group');
    const litellmApiKeyInput = document.getElementById('setup-litellm-api-key');

    function setGroupEnabled(group, input, enabled) {
        if (!group || !input) return;
        group.style.opacity = enabled ? '' : '0.5';
        input.disabled = !enabled;
    }

    function ollamaConfigured() {
        return ollamaModelInput && ollamaModelInput.value.trim().length > 0;
    }

    function litellmConfigured() {
        return litellmModelInput && litellmModelInput.value.trim().length > 0;
    }

    function anthropicConfigured() {
        return anthropicKeyInput && anthropicKeyInput.value.trim().length > 0;
    }

    function syncProviderGroups() {
        setGroupEnabled(ollamaBaseUrlGroup, ollamaBaseUrlInput, ollamaConfigured());
        const litellmOn = litellmConfigured();
        setGroupEnabled(litellmBaseUrlGroup, litellmBaseUrlInput, litellmOn);
        setGroupEnabled(litellmApiKeyGroup, litellmApiKeyInput, litellmOn);
    }

    // -- Default-provider radio gating --------------------------------------

    const defaultRadios = form.querySelectorAll('input[data-default-provider-radio]');

    function syncDefaultProviderRadios() {
        const enabled = {
            anthropic: anthropicConfigured(),
            ollama: ollamaConfigured(),
            litellm: litellmConfigured(),
        };

        defaultRadios.forEach((radio) => {
            const provider = radio.dataset.defaultProviderRadio;
            radio.disabled = !enabled[provider];
            // Grey out the visible label so the disabled state reads clearly.
            const wrapper = radio.closest('.pf-v5-c-radio');
            if (wrapper) wrapper.style.opacity = enabled[provider] ? '' : '0.5';
        });

        const checked = form.querySelector('input[name="default_provider"]:checked');
        const enabledCount = Object.values(enabled).filter(Boolean).length;

        // If the currently-checked radio just got disabled, fall back to the
        // first remaining enabled one (or clear if none).
        if (checked && checked.disabled) {
            checked.checked = false;
            const firstEnabled = Array.from(defaultRadios).find((r) => !r.disabled);
            if (firstEnabled) firstEnabled.checked = true;
        }

        // With one provider configured, auto-pin the default to it. The user
        // never sees the radio meaningfully change in this case; the server
        // accepts a blank default_provider when only one provider is set.
        if (enabledCount === 1 && !form.querySelector('input[name="default_provider"]:checked')) {
            const onlyEnabled = Array.from(defaultRadios).find((r) => !r.disabled);
            if (onlyEnabled) onlyEnabled.checked = true;
        }
    }

    [anthropicKeyInput, ollamaModelInput, litellmModelInput].forEach((el) => {
        if (!el) return;
        el.addEventListener('input', () => {
            syncProviderGroups();
            syncDefaultProviderRadios();
        });
    });

    syncProviderGroups();
    syncDefaultProviderRadios();
})();
