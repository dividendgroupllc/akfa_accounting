// Kassa Rasxod — shared state + constants + mode helpers
(function () {
	const ns = window.akfa_kr = window.akfa_kr || {};

	// Tip constants
	ns.TIP_RASXOD = 'Расход';
	ns.TIP_PODOCHOT_PRIXOD = 'Подотчет приход';
	ns.TIP_PODOCHOT_RASXOD = 'Подотчет расход';
	ns.TIP_KOPLASHGA = 'Коплашга';

	// Shared mutable state
	ns.items_data = [];

	// Mode of payment helpers
	ns.is_usd_mode = function (frm) {
		return frm.doc.mode_of_payment === 'Наличный USD H';
	};
	ns.is_uzs_cash_mode = function (frm) {
		return frm.doc.mode_of_payment === 'Наличный UZS H';
	};
	ns.is_uzs_transfer_mode = function (frm) {
		return frm.doc.mode_of_payment === 'Перечисление UZS';
	};

	// Load/save items_data
	ns.load_custom_table = function (frm) {
		if (frm.doc.items_data) {
			try {
				ns.items_data = JSON.parse(frm.doc.items_data);
			} catch (e) {
				ns.items_data = [];
			}
		} else {
			ns.items_data = [];
		}
		ns.render_custom_table(frm);
		ns.calculate_totals(frm);
	};

	ns.save_items_data = function (frm) {
		frm.set_value('items_data', JSON.stringify(ns.items_data));
		ns.calculate_totals(frm);
	};

	ns.refresh_custom_table = function (frm) {
		ns.render_custom_table(frm);
	};
})();
