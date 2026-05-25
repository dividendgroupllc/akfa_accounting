// Kassa Rasxod — API loader functions (frappe.call wrappers)
(function () {
	const ns = window.akfa_kr = window.akfa_kr || {};

	ns.load_podrazdelenie_options = function ($row, selected_value) {
		frappe.call({
			method: 'frappe.client.get_list',
			args: {
				doctype: 'Podrazdelenie',
				fields: ['name', 'podrazdelenie_name'],
				limit_page_length: 0
			},
			callback: function (r) {
				if (r.message) {
					let $select = $row.find('.item-podrazdilenie');
					$select.empty();
					$select.append('<option value="">-</option>');
					r.message.forEach(function (item) {
						let display = item.podrazdelenie_name || item.name;
						let selected = item.name === selected_value ? 'selected' : '';
						$select.append(`<option value="${item.name}" ${selected}>${display}</option>`);
					});
				}
			}
		});
	};

	// 5200 child accounts as expense group options
	ns.load_cost_center_options = function ($row, selected_value) {
		frappe.call({
			method: 'akfa_accounting.akfa_accounting.doctype.kassa_rasxod.kassa_rasxod.get_child_accounts',
			args: { parent_number: '5200' },
			callback: function (r) {
				if (r.message) {
					let $select = $row.find('.item-cost-center');
					$select.empty();
					$select.append('<option value="">-</option>');
					r.message.forEach(function (item) {
						let selected = item.name === selected_value ? 'selected' : '';
						$select.append(`<option value="${item.name}" ${selected}>${item.name}</option>`);
					});
				}
			}
		});
	};

	ns.load_employee_group_options = function ($row, selected_value) {
		frappe.call({
			method: 'frappe.client.get_list',
			args: {
				doctype: 'Employee Group',
				fields: ['name'],
				limit_page_length: 0
			},
			callback: function (r) {
				if (r.message) {
					let $select = $row.find('.item-employee-group');
					$select.empty();
					$select.append('<option value="">-</option>');
					r.message.forEach(function (item) {
						let selected = item.name === selected_value ? 'selected' : '';
						$select.append(`<option value="${item.name}" ${selected}>${item.name}</option>`);
					});
				}
			}
		});
	};

	ns.load_employee_options = function ($row, employee_group, selected_value) {
		frappe.call({
			method: 'akfa_accounting.akfa_accounting.doctype.kassa_rasxod.kassa_rasxod.get_employees_by_group',
			args: { employee_group: employee_group },
			callback: function (r) {
				let $select = $row.find('.item-employee');
				$select.empty();
				$select.append('<option value="">-</option>');
				if (r.message && r.message.length > 0) {
					r.message.forEach(function (item) {
						let display = item.employee_name ? `${item.employee} - ${item.employee_name}` : item.employee;
						let selected = item.employee === selected_value ? 'selected' : '';
						$select.append(`<option value="${item.employee}" ${selected}>${display}</option>`);
					});
				}
			}
		});
	};

	ns.load_party_options = function ($row, selector, party_type, selected_value) {
		frappe.call({
			method: 'frappe.client.get_list',
			args: {
				doctype: party_type,
				fields: ['name'],
				limit_page_length: 0
			},
			callback: function (r) {
				if (r.message) {
					let $select = $row.find(selector);
					$select.empty();
					$select.append('<option value="">-</option>');
					r.message.forEach(function (item) {
						let selected = item.name === selected_value ? 'selected' : '';
						$select.append(`<option value="${item.name}" ${selected}>${item.name}</option>`);
					});
				}
			}
		});
	};

	ns.load_categories = function ($row, parent_account, selected_category) {
		frappe.call({
			method: 'akfa_accounting.akfa_accounting.doctype.kassa_rasxod.kassa_rasxod.get_child_accounts',
			args: { parent_account: parent_account },
			callback: function (r) {
				if (r.message) {
					let $select = $row.find('.item-category');
					$select.empty();
					$select.append('<option value="">-</option>');
					r.message.forEach(function (acc) {
						let selected = acc.name === selected_category ? 'selected' : '';
						$select.append(`<option value="${acc.name}" ${selected}>${acc.name}</option>`);
					});
				}
			}
		});
	};
})();
