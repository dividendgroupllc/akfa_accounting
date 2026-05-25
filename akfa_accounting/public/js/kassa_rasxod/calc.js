// Kassa Rasxod — calculations + exchange rate + balance fetchers
(function () {
	const ns = window.akfa_kr = window.akfa_kr || {};

	ns.get_exchange_rate = function (frm) {
		if (!frm.doc.posting_date) return;

		frappe.call({
			method: 'frappe.client.get_value',
			args: {
				doctype: 'Currency Exchange',
				filters: {
					from_currency: 'USD',
					to_currency: 'UZS',
					date: frm.doc.posting_date
				},
				fieldname: 'exchange_rate'
			},
			callback: function (r) {
				if (r.message && r.message.exchange_rate) {
					frm.set_value('currency_exchange_rate', r.message.exchange_rate);
				} else {
					// Fallback: most recent rate before/on posting_date
					frappe.call({
						method: 'frappe.client.get_list',
						args: {
							doctype: 'Currency Exchange',
							filters: [
								['from_currency', '=', 'USD'],
								['to_currency', '=', 'UZS'],
								['date', '<=', frm.doc.posting_date]
							],
							fields: ['exchange_rate', 'date'],
							order_by: 'date desc',
							limit_page_length: 1
						},
						callback: function (res) {
							if (res.message && res.message.length > 0) {
								let rate = res.message[0];
								frm.set_value('currency_exchange_rate', rate.exchange_rate);
								frappe.show_alert({
									message: __('Using exchange rate from {0}', [frappe.datetime.str_to_user(rate.date)]),
									indicator: 'blue'
								});
							} else {
								frappe.msgprint({
									title: __('Exchange Rate Missing'),
									indicator: 'red',
									message: __('No Currency Exchange rate found for USD to UZS. Please add an exchange rate first.')
								});
								frm.set_value('currency_exchange_rate', 0);
							}
						}
					});
				}
			}
		});
	};

	ns.get_account_balance = function (frm) {
		if (!frm.doc.mode_of_payment) {
			frm.set_value('balance', 0);
			return;
		}

		frappe.call({
			method: 'akfa_accounting.akfa_accounting.doctype.kassa_rasxod.kassa_rasxod.get_mode_of_payment_balance',
			args: {
				mode_of_payment: frm.doc.mode_of_payment,
				posting_date: frm.doc.posting_date
			},
			callback: function (r) {
				if (r.message !== undefined) {
					frm.set_value('balance', r.message);
					ns.calculate_totals(frm);
				}
			}
		});
	};

	// Sync non-overridden rows to new global rate (UZS mode only)
	ns.recalculate_all_amounts = function (frm) {
		if (!ns.is_usd_mode(frm) && frm.doc.currency_exchange_rate) {
			let global_rate = frm.doc.currency_exchange_rate;
			ns.items_data.forEach(function (item) {
				if (!item._kurs_overridden) {
					item.currency_exchange_rate = global_rate;
					if (item.paid_amount_uzs) {
						item.paid_amount_usd = item.paid_amount_uzs / global_rate;
					}
				}
			});
			ns.save_items_data(frm);
			ns.refresh_custom_table(frm);
		}
	};

	ns.calculate_totals = function (frm) {
		let total_amount = 0;
		let podochot_prixod_sum = 0;
		let koplashga_plus = 0;

		let usd_mode = ns.is_usd_mode(frm);
		let global_rate = frm.doc.currency_exchange_rate || 1;

		ns.items_data.forEach(function (item) {
			let summa_usd;
			if (usd_mode) {
				summa_usd = item.paid_amount_usd || 0;
			} else {
				// UZS mode — convert to USD using per-row rate (fallback to global)
				let row_rate = item.currency_exchange_rate || global_rate;
				let uzs_amount = item.paid_amount_uzs || 0;
				summa_usd = row_rate ? uzs_amount / row_rate : 0;
			}

			if (item.rasxod_podochot === ns.TIP_RASXOD) {
				if (!item.party_type || !item.party) {
					total_amount += summa_usd;
				}
			} else if (item.rasxod_podochot === ns.TIP_PODOCHOT_PRIXOD) {
				podochot_prixod_sum += summa_usd;
			} else if (item.rasxod_podochot === ns.TIP_PODOCHOT_RASXOD) {
				total_amount += summa_usd;
			} else if (item.rasxod_podochot === ns.TIP_KOPLASHGA) {
				let has_party1 = item.party_type && item.party;
				let has_party2 = item.party_type_2 && item.party_2;

				if (has_party1 && has_party2) {
					// Both filled — no effect on balance
				} else if (has_party1 && !has_party2) {
					koplashga_plus += summa_usd;
				} else if (!has_party1 && has_party2) {
					total_amount += summa_usd;
				}
			}
		});

		frm.set_value('total_amount', total_amount);

		let balance = frm.doc.balance || 0;
		let qoldi = balance + podochot_prixod_sum + koplashga_plus - total_amount;
		frm.set_value('qoldi', qoldi);
	};
})();
