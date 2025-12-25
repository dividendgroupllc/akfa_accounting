// Expense Claim customizations
// Auto-fill employee, company, and currency from Trip Master

frappe.ui.form.on('Expense Claim', {
	setup: function(frm) {
		// Auto-fill employee on new document
		if (frm.is_new()) {
			frappe.call({
				method: 'frappe.client.get_value',
				args: {
					doctype: 'Employee',
					filters: { user_id: frappe.session.user },
					fieldname: ['name', 'employee_name', 'company']
				},
				callback: function(r) {
					if (r.message) {
						frm.set_value('employee', r.message.name);
						frm.set_value('employee_name', r.message.employee_name);
						frm.set_value('company', r.message.company);
					}
				}
			});
		}
	},

	onload: function(frm) {
		// Set currency from Trip Master or Company
		if (frm.is_new() && !frm.doc.custom_currency) {
			setTimeout(function() {
				if (frm.doc.custom_trip_master) {
					// If Trip Master is set, fetch its currency
					frappe.call({
						method: 'frappe.client.get_value',
						args: {
							doctype: 'Trip Master',
							name: frm.doc.custom_trip_master,
							fieldname: 'currency'
						},
						callback: function(r) {
							if (r.message && r.message.currency) {
								frm.set_value('custom_currency', r.message.currency);
							}
						}
					});
				} else if (frm.doc.company) {
					// Otherwise use company default currency
					frappe.call({
						method: 'frappe.client.get_value',
						args: {
							doctype: 'Company',
							name: frm.doc.company,
							fieldname: 'default_currency'
						},
						callback: function(r) {
							if (r.message && r.message.default_currency) {
								frm.set_value('custom_currency', r.message.default_currency);
							}
						}
					});
				}
			}, 500);
		}
	},

	refresh: function(frm) {
		// Show employee info in a nice way if hidden
		if (frm.doc.employee_name && frm.doc.docstatus === 0) {
			frm.dashboard.add_indicator(
				__('Employee: {0}', [frm.doc.employee_name]),
				'blue'
			);
		}

		// Show Trip info if linked
		if (frm.doc.custom_trip_master) {
			frm.dashboard.add_indicator(
				__('Trip: {0}', [frm.doc.custom_trip_master]),
				'green'
			);

			// Add View Budget button for trip members
			if (frm.doc.docstatus < 2) {
				frm.add_custom_button(__('Byudjet'), function() {
					frappe.set_route('trip-monitoring', frm.doc.custom_trip_master, 'budget');
				}, __('Ko\'rish'));
			}
		}
	},

	custom_trip_master: function(frm) {
		// When Trip Master is set, fetch and apply its currency
		if (frm.doc.custom_trip_master) {
			frappe.call({
				method: 'frappe.client.get_value',
				args: {
					doctype: 'Trip Master',
					name: frm.doc.custom_trip_master,
					fieldname: ['currency', 'title']
				},
				callback: function(r) {
					if (r.message && r.message.currency) {
						// Set parent currency field
						frm.set_value('custom_currency', r.message.currency);

						// Update existing rows
						if (frm.doc.expenses && frm.doc.expenses.length > 0) {
							frm.doc.expenses.forEach(function(row) {
								frappe.model.set_value(row.doctype, row.name, 'custom_currency', r.message.currency);
							});
						}

						frappe.show_alert({
							message: __('Trip valyutasi: {0}', [r.message.currency]),
							indicator: 'blue'
						});
					}
				}
			});
		}
	},

	custom_currency: function(frm) {
		// When currency changes, update all child table rows
		if (frm.doc.custom_currency && frm.doc.expenses) {
			frm.doc.expenses.forEach(function(row) {
				frappe.model.set_value(row.doctype, row.name, 'custom_currency', frm.doc.custom_currency);
			});
			frm.refresh_field('expenses');
		}
	}
});

// Handle Expense Claim Detail
frappe.ui.form.on('Expense Claim Detail', {
	expenses_add: function(frm, cdt, cdn) {
		// Set default expense date to today
		frappe.model.set_value(cdt, cdn, 'expense_date', frappe.datetime.get_today());

		// Set currency from parent
		if (frm.doc.custom_currency) {
			frappe.model.set_value(cdt, cdn, 'custom_currency', frm.doc.custom_currency);
		}
	},

	expense_type: function(frm, cdt, cdn) {
		// Override default behavior to include company parameter
		var row = locals[cdt][cdn];
		if (row.expense_type && frm.doc.company) {
			frappe.call({
				method: "hrms.hr.doctype.expense_claim.expense_claim.get_expense_claim_account_and_cost_center",
				args: {
					expense_claim_type: row.expense_type,
					company: frm.doc.company
				},
				callback: function(r) {
					if (r.message) {
						frappe.model.set_value(cdt, cdn, "default_account", r.message.account);
						frappe.model.set_value(cdt, cdn, "cost_center", r.message.cost_center);
					}
				}
			});
		}
	}
});
