// Copyright (c) 2025, Asadbek and contributors
// For license information, please see license.txt

frappe.ui.form.on('Trip Master', {
	refresh: function(frm) {
		// Add "View Budget" button for submitted trips
		if (frm.doc.docstatus === 1 && frm.doc.project) {
			frm.add_custom_button(__('View Budget'), function() {
				frappe.call({
					method: 'akfa_accounting.api.get_trip_balance',
					args: {
						trip_id: frm.doc.name
					},
					callback: function(r) {
						if (r.message && r.message.success) {
							let data = r.message;

							// Format currency
							let currency_symbol = data.currency === 'UZS' ? 'so\'m' : data.currency;
							let budget_formatted = format_currency(data.budget, currency_symbol);
							let spent_formatted = format_currency(data.spent, currency_symbol);
							let balance_formatted = format_currency(data.balance, currency_symbol);

							// Determine status color
							let status_color = data.utilization_percent < 70 ? 'green' :
											   data.utilization_percent < 90 ? 'orange' : 'red';

							// Create beautiful dialog
							let d = new frappe.ui.Dialog({
								title: __('Budget Overview - {0}', [data.trip_title]),
								fields: [
									{
										fieldtype: 'HTML',
										fieldname: 'budget_card',
										options: `
											<div style="padding: 20px;">
												<div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
															color: white;
															padding: 25px;
															border-radius: 12px;
															margin-bottom: 20px;
															box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
													<h3 style="margin: 0 0 10px 0; font-size: 18px;">Total Budget</h3>
													<h1 style="margin: 0; font-size: 36px; font-weight: bold;">${budget_formatted}</h1>
												</div>

												<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 20px;">
													<div style="background: #fee;
																padding: 20px;
																border-radius: 10px;
																border-left: 4px solid #f44336;">
														<div style="color: #666; font-size: 12px; margin-bottom: 5px;">SPENT</div>
														<div style="font-size: 24px; font-weight: bold; color: #f44336;">${spent_formatted}</div>
													</div>

													<div style="background: #e8f5e9;
																padding: 20px;
																border-radius: 10px;
																border-left: 4px solid #4caf50;">
														<div style="color: #666; font-size: 12px; margin-bottom: 5px;">BALANCE</div>
														<div style="font-size: 24px; font-weight: bold; color: #4caf50;">${balance_formatted}</div>
													</div>
												</div>

												<div style="background: #f5f5f5; padding: 15px; border-radius: 10px;">
													<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
														<span style="font-weight: 500;">Utilization</span>
														<span style="font-weight: bold; color: ${status_color};">${data.utilization_percent}%</span>
													</div>
													<div style="background: #ddd;
																height: 10px;
																border-radius: 5px;
																overflow: hidden;">
														<div style="background: ${status_color};
																	height: 100%;
																	width: ${data.utilization_percent}%;
																	border-radius: 5px;
																	transition: width 0.3s ease;"></div>
													</div>
												</div>

												<div style="margin-top: 20px; padding: 15px; background: #e3f2fd; border-radius: 10px;">
													<div style="display: flex; justify-content: space-between;">
														<span><strong>Trip Status:</strong></span>
														<span style="color: #1976d2; font-weight: bold;">${data.status}</span>
													</div>
												</div>
											</div>
										`
									}
								],
								primary_action_label: __('Close'),
								primary_action: function() {
									d.hide();
								}
							});

							d.show();
						} else {
							frappe.msgprint({
								title: __('Error'),
								message: r.message ? r.message.error : __('Failed to fetch budget data'),
								indicator: 'red'
							});
						}
					},
					error: function(r) {
						frappe.msgprint({
							title: __('Error'),
							message: __('Failed to connect to budget API'),
							indicator: 'red'
						});
					}
				});
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

		// Live map renderer for submitted trips
		if (frm.doc.docstatus === 1) {
			render_live_map(frm);
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

function render_live_map(frm) {
	const field = frm.get_field('live_map_html');
	if (!field) return;

	const wrapper = field.$wrapper;
	wrapper.html('<div id="trip-live-map" style="height:360px;border:1px solid #e5e7eb;border-radius:8px;"></div>');

	frappe.call({
		method: 'akfa_accounting.api.get_trip_path',
		args: { trip_master: frm.doc.name },
		callback: (r) => {
			const points = (r.message || []).filter(p => p.latitude && p.longitude);
			if (!points.length) {
				wrapper.html(__('Check-in loglari yo\'q'));
				return;
			}
			load_leaflet(() => draw_trip_polyline(points));
		}
	});
}

function load_leaflet(done) {
	ensure_leaflet_css();
	if (window.L) {
		done();
		return;
	}
	frappe.require('assets/frappe/js/lib/leaflet/leaflet.js', () => done());
}

function ensure_leaflet_css() {
	if (document.getElementById('leaflet-css')) return;
	const link = document.createElement('link');
	link.id = 'leaflet-css';
	link.rel = 'stylesheet';
	link.href = '/assets/frappe/css/leaflet.css';
	document.head.appendChild(link);
}

function draw_trip_polyline(points) {
	const coords = points.map(p => [parseFloat(p.latitude), parseFloat(p.longitude)]);
	const map = L.map('trip-live-map');
	L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '&copy; OpenStreetMap' }).addTo(map);

	const polyline = L.polyline(coords, { color: '#e11d48', weight: 4, opacity: 0.9 }).addTo(map);
	coords.forEach((pt, idx) => {
		L.circleMarker(pt, { radius: 5, color: '#1d4ed8', fillColor: '#1d4ed8', fillOpacity: 0.9 })
			.bindPopup(`${points[idx].employee_name || ''}<br>${points[idx].timestamp || ''}`)
			.addTo(map);
	});

	map.fitBounds(polyline.getBounds(), { padding: [12, 12] });
}
