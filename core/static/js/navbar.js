/**
 * Navbar functionality - user dropdown menu
 */

document.addEventListener('DOMContentLoaded', function() {
    const dropdown = document.getElementById('user-dropdown');
    const toggle = document.getElementById('user-dropdown-toggle');
    const menu = document.getElementById('user-dropdown-menu');

    if (!dropdown || !toggle || !menu) {
        return; // Elements not found (user not authenticated)
    }

    // Toggle dropdown on button click
    toggle.addEventListener('click', function(e) {
        e.stopPropagation();
        const isExpanded = toggle.getAttribute('aria-expanded') === 'true';

        if (isExpanded) {
            closeDropdown();
        } else {
            openDropdown();
        }
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', function(e) {
        if (!dropdown.contains(e.target)) {
            closeDropdown();
        }
    });

    // Close dropdown on escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeDropdown();
        }
    });

    function openDropdown() {
        toggle.setAttribute('aria-expanded', 'true');
        menu.removeAttribute('hidden');
        dropdown.classList.add('pf-m-expanded');
    }

    function closeDropdown() {
        toggle.setAttribute('aria-expanded', 'false');
        menu.setAttribute('hidden', '');
        dropdown.classList.remove('pf-m-expanded');
    }
});
