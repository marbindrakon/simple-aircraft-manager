(function () {
    var root = document.documentElement;
    var pref = root.getAttribute('data-theme-pref') || 'system';
    var mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');

    function applyTheme(p) {
        root.setAttribute('data-theme-pref', p);
        if (p === 'dark') {
            root.classList.add('pf-v5-theme-dark');
        } else if (p === 'light') {
            root.classList.remove('pf-v5-theme-dark');
        } else {
            // system
            if (mediaQuery.matches) {
                root.classList.add('pf-v5-theme-dark');
            } else {
                root.classList.remove('pf-v5-theme-dark');
            }
        }
    }

    function setCookie(p) {
        var expires = new Date();
        expires.setFullYear(expires.getFullYear() + 1);
        document.cookie = 'theme_pref=' + p + '; expires=' + expires.toUTCString() + '; path=/; SameSite=Strict';
    }

    function closeUserDropdown() {
        var menu = document.getElementById('user-dropdown-menu');
        var toggle = document.getElementById('user-dropdown-toggle');
        var dd = document.getElementById('user-dropdown');
        if (menu) menu.setAttribute('hidden', '');
        if (toggle) toggle.setAttribute('aria-expanded', 'false');
        if (dd) dd.classList.remove('pf-m-expanded');
    }

    // Apply theme immediately (handles system mode; dark/light already correct from server-side)
    if (pref === 'system') {
        applyTheme('system');
    }

    // Listen for OS preference changes when in system mode
    mediaQuery.addEventListener('change', function () {
        if (root.getAttribute('data-theme-pref') === 'system') {
            applyTheme('system');
        }
    });

    document.addEventListener('DOMContentLoaded', function () {
        // Dropdown theme options (main authenticated navbar)
        var options = document.querySelectorAll('.theme-option[data-theme-value]');
        options.forEach(function (btn) {
            btn.addEventListener('click', function () {
                var next = btn.getAttribute('data-theme-value');
                setCookie(next);
                applyTheme(next);
                closeUserDropdown();
            });
        });

        // Cycling button (public page masthead)
        var cycleBtn = document.getElementById('theme-toggle-btn');
        if (cycleBtn) {
            cycleBtn.addEventListener('click', function () {
                var current = root.getAttribute('data-theme-pref') || 'system';
                var next = current === 'light' ? 'dark' : current === 'dark' ? 'system' : 'light';
                setCookie(next);
                applyTheme(next);
            });
        }
    });
})();
