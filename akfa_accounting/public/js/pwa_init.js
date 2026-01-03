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

// For now, just log that the file loaded successfully
console.log('AKFA Accounting: PWA init loaded');
