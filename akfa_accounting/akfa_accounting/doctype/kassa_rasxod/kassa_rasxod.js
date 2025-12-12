frappe.ui.form.on('Kassa Rasxod', {
	onload: function(frm) {
		// Set currency exchange rate on load
		if (!frm.doc.currency_exchange_rate) {
			get_exchange_rate(frm);
		}
	},
	
	posting_date: function(frm) {
		// Get exchange rate when date changes
		get_exchange_rate(frm);
	},
	
	podrazdelenie: function(frm) {
		// Get employee when podrazdelenie changes
		get_employee(frm);
	},
	
	mode_of_payment: function(frm) {
		// Reset amounts when mode changes
		frm.set_value('paid_amount_uzs', 0);
		frm.set_value('paid_amount_usd', 0);
		
		// Get exchange rate
		get_exchange_rate(frm);
		
		// Set field properties based on mode of payment
		if (frm.doc.mode_of_payment) {
			let mop = frm.doc.mode_of_payment;
			
			// Наличные USD -> enter USD, calculate UZS
			if (mop === 'Наличные USD') {
				frm.set_df_property('paid_amount_usd', 'read_only', 0);
				frm.set_df_property('paid_amount_usd', 'reqd', 1);
				frm.set_df_property('paid_amount_uzs', 'read_only', 1);
				frm.set_df_property('paid_amount_uzs', 'reqd', 0);
			} 
			// Наличные UZS, Перечисления UZS -> enter UZS, calculate USD
			else if (mop === 'Наличные UZS' || mop === 'Перечисления UZS') {
				frm.set_df_property('paid_amount_uzs', 'read_only', 0);
				frm.set_df_property('paid_amount_uzs', 'reqd', 1);
				frm.set_df_property('paid_amount_usd', 'read_only', 1);
				frm.set_df_property('paid_amount_usd', 'reqd', 0);
			}
			// Default - enter UZS
			else {
				frm.set_df_property('paid_amount_uzs', 'read_only', 0);
				frm.set_df_property('paid_amount_uzs', 'reqd', 1);
				frm.set_df_property('paid_amount_usd', 'read_only', 1);
				frm.set_df_property('paid_amount_usd', 'reqd', 0);
			}
		}
	},
	
	cost_center: function(frm) {
		// Clear category when cost center changes
		frm.set_value('category', '');
		
		if (frm.doc.cost_center) {
			// Get categories for selected cost center
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
		if (mop && (mop === 'Наличные UZS' || mop === 'Перечисления UZS')) {
			calculate_usd_amount(frm);
		}
	},
	
	paid_amount_usd: function(frm) {
		let mop = frm.doc.mode_of_payment;
		if (mop && mop === 'Наличные USD') {
			calculate_uzs_amount(frm);
		}
	},
	
	currency_exchange_rate: function(frm) {
		if (frm.doc.mode_of_payment === 'Nalichniy USD' && frm.doc.paid_amount_usd) {
			calculate_uzs_amount(frm);
		} else if (frm.doc.paid_amount_uzs) {
			calculate_usd_amount(frm);
		}
	}
});

function get_exchange_rate(frm) {
	if (!frm.doc.posting_date) {
		return;
	}
	
	// Check if exchange rate exists in Currency Exchange
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
				// Show warning if exchange rate not found
				frappe.msgprint({
					title: __('Exchange Rate Missing'),
					indicator: 'red',
					message: __('Currency Exchange rate for USD to UZS on {0} not found. Please add the exchange rate in Currency Exchange first.', 
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
	
	// Get employee from Employee Podrazdelenie based on date and podrazdelenie
	frappe.call({
		method: 'frappe.client.get_value',
		args: {
			doctype: 'Employee Podrazdelenie',
			filters: {
				date: frm.doc.posting_date,
				podrazdelenie: frm.doc.podrazdelenie
			},
			fieldname: ['employee']
		},
		callback: function(r) {
			if (r.message && r.message.employee) {
				frm.set_value('employee', r.message.employee);
				
				// Get employee full name
				frappe.db.get_value('Employee', r.message.employee, ['first_name', 'last_name'], (emp) => {
					if (emp) {
						let full_name = (emp.first_name || '') + ' ' + (emp.last_name || '');
						frm.set_value('employee_name', full_name.trim());
					}
				});
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
