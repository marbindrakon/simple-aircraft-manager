/**
 * Admin theme initializer — runs synchronously in <head> before first paint.
 * Reads the theme_pref cookie (set by the main app's theme toggle) and applies
 * the pf-v5-theme-dark class to <html> so PatternFly CSS variables resolve
 * correctly on initial render.
 */
(function () {
    var root = document.documentElement;

    function getCookieValue(name) {
        var match = document.cookie.match('(?:^|; )' + name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '=([^;]*)');
        return match ? decodeURIComponent(match[1]) : null;
    }

    var pref = getCookieValue('theme_pref') || 'system';
    root.setAttribute('data-theme-pref', pref);

    if (pref === 'dark') {
        root.classList.add('pf-v5-theme-dark');
    } else if (pref === 'system') {
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
            root.classList.add('pf-v5-theme-dark');
        }
        // Watch for OS preference changes
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function (e) {
            if (root.getAttribute('data-theme-pref') === 'system') {
                if (e.matches) {
                    root.classList.add('pf-v5-theme-dark');
                } else {
                    root.classList.remove('pf-v5-theme-dark');
                }
            }
        });
    }
    // pref === 'light': no class needed, light is the default
})();
