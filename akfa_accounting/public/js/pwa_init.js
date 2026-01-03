// PWA Init - Register Service Worker
$(document).ready(function () {
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/assets/akfa_accounting/sw.js').then(function (reg) {
            console.log('SW registered:', reg.scope);
        }).catch(function (err) {
            console.log('SW failed:', err);
        });
    }
});
