// Kassa Rasxod — form event entry point.
// Helper modules live in akfa_accounting/public/js/kassa_rasxod/*.js (loaded via hooks.py doctype_js).
// All shared state and helpers live on window.akfa_kr namespace.

frappe.ui.form.on('Kassa Rasxod', {
	onload: function (frm) {
		if (!frm.doc.currency_exchange_rate) {
			akfa_kr.get_exchange_rate(frm);
		}
		akfa_kr.load_custom_table(frm);
	},

	refresh: function (frm) {
		akfa_kr.load_custom_table(frm);
	},

	posting_date: function (frm) {
		akfa_kr.get_exchange_rate(frm);
	},

	mode_of_payment: function (frm) {
		akfa_kr.get_exchange_rate(frm);
		akfa_kr.get_account_balance(frm);
		akfa_kr.refresh_custom_table(frm);
	},

	currency_exchange_rate: function (frm) {
		akfa_kr.recalculate_all_amounts(frm);
	}
});
