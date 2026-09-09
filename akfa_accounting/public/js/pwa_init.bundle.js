// PWA Init - Service Worker disabled for development
// To enable in production, uncomment the code below

/*
$(document).ready(function() {
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/assets/akfa_accounting/sw.js').then(function(reg) {
            console.log('SW registered:', reg.scope);
        }).catch(function(err) {
            console.log('SW failed:', err);
        });
    }
});
*/

// Send field employees straight to Mobile HR when they open the desk on a phone.
//
// This has to run in the browser. The `on_login` hook cannot do it: the login
// page only follows `home_page`, which `set_user_info()` rewrites after the hook
// runs, and a user returning with a live session never triggers a login at all.
(function () {
    // Office staff keep the full desk on every device.
    var BACK_OFFICE_ROLES = [
        'System Manager',
        'HR Manager',
        'HR User',
        'Accounts Manager',
        'Accounts User',
    ];

    var SEEN_KEY = 'akfa_mobile_hr_redirected';

    function is_field_employee() {
        return frappe.user.has_role('Employee') && !frappe.user.has_role(BACK_OFFICE_ROLES);
    }

    // Only take over the landing page, never a route the user chose themselves.
    // Read the URL rather than frappe.get_route(): the router is still resolving
    // when app_ready fires, so the route object can lag behind the address bar.
    function is_landing_route() {
        var path = (window.location.pathname || '').replace(/\/+$/, '');
        return path === '/app' || path === '/app/home';
    }

    function already_redirected() {
        try {
            return sessionStorage.getItem(SEEN_KEY) === '1';
        } catch (e) {
            return false; // private mode: redirect once per page load instead
        }
    }

    function mark_redirected() {
        try {
            sessionStorage.setItem(SEEN_KEY, '1');
        } catch (e) {
            // ignore
        }
    }

    $(document).on('app_ready', function () {
        if (already_redirected()) return;
        if (!frappe.is_mobile()) return;
        if (!is_field_employee()) return;
        if (!is_landing_route()) return;

        mark_redirected();
        frappe.set_route('mobile-hr');
    });
})();
