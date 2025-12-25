// Copyright (c) 2025, Asadbek and contributors
// For license information, please see license.txt

frappe.ui.form.on('Trip Master', {
	refresh: function(frm) {
		// Add monitoring button for submitted trips
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__('📊 Monitor Trip'), function() {
				frappe.set_route('trip-monitoring', frm.doc.name);
			}, __('Dashboard'));

			frm.add_custom_button(__('💰 View Budget'), function() {
				frappe.set_route('trip-monitoring', frm.doc.name, 'budget');
			}, __('Dashboard'));
		}

		// Add "Complete Trip" action for active trips
		if (frm.doc.docstatus === 1 && frm.doc.status === "Active") {
			frm.add_custom_button(__('Complete Trip'), () => {
				frm.call('complete_trip').then((r) => {
					if (r && r.message && r.message.status === "Completed") {
						frappe.show_alert({ message: __('Trip marked as Completed'), indicator: 'green' });
						frm.reload_doc();
					}
				}).catch(() => {
					frappe.show_alert({ message: __('Failed to complete trip'), indicator: 'red' });
				});
			}, __('Actions'));
		}
	},

	onload: function(frm) {
		// Set default financial accounts from Company
		if (frm.doc.company && !frm.doc.advance_account) {
			frappe.db.get_value('Company', frm.doc.company, 'default_employee_advance_account', (r) => {
				if (r && r.default_employee_advance_account) {
					frm.set_value('advance_account', r.default_employee_advance_account);
				}
			});
		}
	},

	company: function(frm) {
		// Update defaults when company changes
		if (frm.doc.company) {
			// Set default advance account
			if (!frm.doc.advance_account) {
				frappe.db.get_value('Company', frm.doc.company, 'default_employee_advance_account', (r) => {
					if (r && r.default_employee_advance_account) {
						frm.set_value('advance_account', r.default_employee_advance_account);
					}
				});
			}

			// Set default cost center
			if (!frm.doc.cost_center) {
				frappe.db.get_value('Company', frm.doc.company, 'cost_center', (r) => {
					if (r && r.cost_center) {
						frm.set_value('cost_center', r.cost_center);
					}
				});
			}
		}
	},

	employee_group: function(frm) {
		// Auto-load employees when sector (Employee Group) changes
		if (frm.doc.employee_group) {
			frappe.call({
				method: 'akfa_accounting.akfa_accounting.doctype.trip_master.trip_master.get_employees_from_group',
				args: {
					employee_group: frm.doc.employee_group
				},
				callback: function(r) {
					if (r.message && r.message.length > 0) {
						// Clear existing members
						frm.clear_table('members');

						// Add all employees from the group
						r.message.forEach(function(emp_row) {
							if (emp_row.employee) {
								let row = frm.add_child('members');
								row.employee = emp_row.employee;
								row.employee_name = emp_row.employee_name;
								row.is_traveling = 0;
								row.is_leader = 0;
							}
						});

						frm.refresh_field('members');

						frappe.show_alert({
							message: __('Loaded {0} employees from {1}', [r.message.length, frm.doc.employee_group]),
							indicator: 'green'
						}, 5);
					} else {
						frappe.msgprint({
							title: __('No Employees Found'),
							message: __('No employees found in {0}', [frm.doc.employee_group]),
							indicator: 'orange'
						});
					}
				},
				error: function(r) {
					frappe.msgprint({
						title: __('Error'),
						message: __('Failed to load employees from Employee Group'),
						indicator: 'red'
					});
					console.error('Employee Group load error:', r);
				}
			});
		}
	},

	cost_center: function(frm) {
		// Filter accounts by cost center's company
		if (frm.doc.cost_center && frm.doc.company) {
			frm.set_query('payment_account', function() {
				return {
					filters: {
						'company': frm.doc.company,
						'account_type': ['in', ['Bank', 'Cash']],
						'is_group': 0
					}
				};
			});

			frm.set_query('advance_account', function() {
				return {
					filters: {
						'company': frm.doc.company,
						'account_type': 'Receivable',
						'is_group': 0
					}
				};
			});
		}
	}
});
