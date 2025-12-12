frappe.ui.form.on('Kassa Rasxod', {
	onload: function(frm) {
		if (!frm.doc.currency_exchange_rate) {
			get_exchange_rate(frm);
		}
	},

	posting_date: function(frm) {
		get_exchange_rate(frm);
		get_employee(frm);
	},

	podrazdelenie: function(frm) {
		get_employee(frm);
	},

	mode_of_payment: function(frm) {
		frm.set_value('paid_amount_uzs', 0);
		frm.set_value('paid_amount_usd', 0);

		get_exchange_rate(frm);
		get_payment_account(frm);

		if (frm.doc.mode_of_payment) {
			let mop = frm.doc.mode_of_payment;

			if (mop === 'Наличные USD' || mop === 'Наличный USD H') {
				frm.set_df_property('paid_amount_usd', 'read_only', 0);
				frm.set_df_property('paid_amount_usd', 'reqd', 1);
				frm.set_df_property('paid_amount_uzs', 'read_only', 1);
				frm.set_df_property('paid_amount_uzs', 'reqd', 0);
			} else {
				frm.set_df_property('paid_amount_uzs', 'read_only', 0);
				frm.set_df_property('paid_amount_uzs', 'reqd', 1);
				frm.set_df_property('paid_amount_usd', 'read_only', 1);
				frm.set_df_property('paid_amount_usd', 'reqd', 0);
			}
		}
	},

	cost_center: function(frm) {
		frm.set_value('category', '');

		if (frm.doc.cost_center) {
			frappe.call({
				method: 'frappe.client.get',
				args: {
					doctype: 'Custom Cost Center',
					name: frm.doc.cost_center
				},
				callback: function(r) {
					if (r.message && r.message.categories) {
						let categories = r.message.categories.map(d => d.category_name);
						frm.set_df_property('category', 'options', categories.join('\n'));
					}
				}
			});
		}
	},

	paid_amount_uzs: function(frm) {
		let mop = frm.doc.mode_of_payment;
		if (mop && mop !== 'Наличные USD' && mop !== 'Наличный USD H') {
			calculate_usd_amount(frm);
		}
	},

	paid_amount_usd: function(frm) {
		let mop = frm.doc.mode_of_payment;
		if (mop && (mop === 'Наличные USD' || mop === 'Наличный USD H')) {
			calculate_uzs_amount(frm);
		}
	},

	currency_exchange_rate: function(frm) {
		let mop = frm.doc.mode_of_payment;
		if (mop === 'Наличные USD' || mop === 'Наличный USD H') {
			if (frm.doc.paid_amount_usd) {
				calculate_uzs_amount(frm);
			}
		} else if (frm.doc.paid_amount_uzs) {
			calculate_usd_amount(frm);
		}
	}
});

function get_exchange_rate(frm) {
	if (!frm.doc.posting_date) {
		return;
	}

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
		callback: function(r) {
			if (r.message && r.message.exchange_rate) {
				frm.set_value('currency_exchange_rate', r.message.exchange_rate);
			} else {
				frappe.msgprint({
					title: __('Exchange Rate Missing'),
					indicator: 'red',
					message: __('Currency Exchange rate for USD to UZS on {0} not found.',
						[frappe.datetime.str_to_user(frm.doc.posting_date)])
				});
				frm.set_value('currency_exchange_rate', 0);
			}
		}
	});
}

function calculate_usd_amount(frm) {
	if (frm.doc.paid_amount_uzs && frm.doc.currency_exchange_rate) {
		let usd_amount = frm.doc.paid_amount_uzs / frm.doc.currency_exchange_rate;
		frm.set_value('paid_amount_usd', usd_amount);
	}
}

function calculate_uzs_amount(frm) {
	if (frm.doc.paid_amount_usd && frm.doc.currency_exchange_rate) {
		let uzs_amount = frm.doc.paid_amount_usd * frm.doc.currency_exchange_rate;
		frm.set_value('paid_amount_uzs', uzs_amount);
	}
}

function get_employee(frm) {
	if (!frm.doc.posting_date || !frm.doc.podrazdelenie) {
		return;
	}

	// Eng so'nggi employee record ni olish (date <= posting_date)
	frappe.call({
		method: 'akfa_accounting.akfa_accounting.doctype.kassa_rasxod.kassa_rasxod.get_employee_for_date',
		args: {
			posting_date: frm.doc.posting_date,
			podrazdelenie: frm.doc.podrazdelenie
		},
		callback: function(r) {
			if (r.message) {
				frm.set_value('employee', r.message.employee);
				frm.set_value('employee_name', r.message.employee_name || '');
			} else {
				frappe.msgprint({
					title: __('Employee Not Found'),
					indicator: 'orange',
					message: __('No employee found for {0} on {1}',
						[frm.doc.podrazdelenie, frappe.datetime.str_to_user(frm.doc.posting_date)])
				});
				frm.set_value('employee', '');
				frm.set_value('employee_name', '');
			}
		}
	});
}

function get_payment_account(frm) {
	if (!frm.doc.mode_of_payment) {
		frm.set_value('payment_account', '');
		frm.set_value('account_balance', 0);
		return;
	}

	frappe.call({
		method: 'akfa_accounting.akfa_accounting.doctype.kassa_rasxod.kassa_rasxod.get_mode_of_payment_account',
		args: {
			mode_of_payment: frm.doc.mode_of_payment,
			company: 'Akfa'
		},
		callback: function(r) {
			if (r.message) {
				frm.set_value('payment_account', r.message.account);
				frm.set_value('account_balance', r.message.balance || 0);
			} else {
				frm.set_value('payment_account', '');
				frm.set_value('account_balance', 0);
			}
		}
	});
}
