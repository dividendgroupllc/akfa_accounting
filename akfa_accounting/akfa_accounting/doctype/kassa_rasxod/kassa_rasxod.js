frappe.ui.form.on('Kassa Rasxod', {
	onload: function(frm) {
		if (!frm.doc.currency_exchange_rate) {
			get_exchange_rate(frm);
		}
		load_custom_table(frm);
	},

	refresh: function(frm) {
		load_custom_table(frm);
	},

	posting_date: function(frm) {
		get_exchange_rate(frm);
	},

	mode_of_payment: function(frm) {
		get_exchange_rate(frm);
		refresh_custom_table(frm);
	},

	currency_exchange_rate: function(frm) {
		recalculate_all_amounts(frm);
	}
});

let items_data = [];

// Mode of payment helpers
function is_usd_mode(frm) {
	return frm.doc.mode_of_payment === 'Наличный USD H';
}

function is_uzs_cash_mode(frm) {
	return frm.doc.mode_of_payment === 'Наличный UZS H';
}

function is_uzs_transfer_mode(frm) {
	return frm.doc.mode_of_payment === 'Перечисление UZS';
}

function is_cash_mode(frm) {
	return is_usd_mode(frm) || is_uzs_cash_mode(frm);
}

function load_custom_table(frm) {
	// Load data from hidden field
	if (frm.doc.items_data) {
		try {
			items_data = JSON.parse(frm.doc.items_data);
		} catch(e) {
			items_data = [];
		}
	} else {
		items_data = [];
	}

	render_custom_table(frm);
}

function save_items_data(frm) {
	frm.set_value('items_data', JSON.stringify(items_data));
}

function get_visible_columns(frm) {
	// Base columns always visible
	let columns = [
		{ key: 'idx', label: '#', width: '40px' },
		{ key: 'izoh', label: 'Изох', width: '150px' },
		{ key: 'podrazdilenie', label: 'Подразделение', width: '120px' },
		{ key: 'rasxod_podochot', label: 'Тип', width: '100px' }
	];

	// Conditional columns will be added per row
	return columns;
}

function render_custom_table(frm) {
	let container = frm.fields_dict.custom_items_html.$wrapper;
	container.empty();

	let mode_selected = frm.doc.mode_of_payment ? true : false;
	let usd_mode = is_usd_mode(frm);
	let uzs_mode = is_uzs_cash_mode(frm);

	let html = `
		<style>
			.custom-table-container {
				margin: 15px 0;
				overflow-x: auto;
			}
			.custom-items-table {
				width: 100%;
				border-collapse: separate;
				border-spacing: 0;
				font-size: 13px;
				border: 1px solid #d1d8dd;
				border-radius: 4px;
			}
			.custom-items-table th {
				background: linear-gradient(to bottom, #fafbfc, #f1f3f5);
				border-bottom: 2px solid #d1d8dd;
				border-right: 1px solid #e8e8e8;
				padding: 10px 8px;
				text-align: center;
				font-weight: 600;
				color: #333;
				font-size: 12px;
				white-space: nowrap;
			}
			.custom-items-table th:last-child {
				border-right: none;
			}
			.custom-items-table td {
				border-bottom: 1px solid #e8e8e8;
				border-right: 1px solid #e8e8e8;
				padding: 6px 8px;
				vertical-align: middle;
				background: #fff;
			}
			.custom-items-table td:last-child {
				border-right: none;
			}
			.custom-items-table tr:last-child td {
				border-bottom: none;
			}
			.custom-items-table tr:hover td {
				background-color: #f8f9fa;
			}
			.custom-items-table input,
			.custom-items-table select,
			.custom-items-table textarea {
				width: 100%;
				border: 1px solid #d1d8dd;
				border-radius: 3px;
				padding: 6px 10px;
				font-size: 13px;
				transition: border-color 0.15s ease;
				box-sizing: border-box;
			}
			.custom-items-table input:focus,
			.custom-items-table select:focus,
			.custom-items-table textarea:focus {
				border-color: #80bdff;
				outline: none;
				box-shadow: 0 0 0 2px rgba(0,123,255,.1);
			}
			.custom-items-table textarea {
				min-height: 40px;
				resize: vertical;
			}
			.custom-items-table input[readonly] {
				background-color: #e9ecef !important;
				color: #666 !important;
			}
			.btn-add-row {
				margin-top: 12px;
				padding: 6px 14px;
			}
			.btn-delete-row {
				color: #d73737;
				cursor: pointer;
				font-size: 18px;
				font-weight: bold;
				transition: color 0.15s ease;
			}
			.btn-delete-row:hover {
				color: #a00;
			}
			.required-field {
				border-color: #f0ad4e !important;
				background-color: #fffdf5 !important;
			}
			.row-idx {
				text-align: center;
				font-weight: 600;
				color: #666;
				background-color: #fafbfc !important;
			}
			.delete-cell {
				text-align: center;
				background-color: #fafbfc !important;
			}
		</style>
		<div class="custom-table-container">
			<table class="custom-items-table">
				<thead>
					<tr>
						<th style="width: 40px;">#</th>
						<th style="width: 150px;">Изох</th>
						<th style="width: 140px;">Подразделение</th>
						<th style="width: 110px;">Тип</th>
						<th class="th-cost-center" style="width: 150px;">Cost Center</th>
						<th class="th-category" style="width: 130px;">Тип 1</th>
						<th class="th-sektor" style="width: 140px;">Сектор</th>
						<th class="th-employee" style="width: 150px;">Сотрудник</th>
						<th class="th-uzs" style="width: 120px;">Сумма UZS</th>
						<th class="th-usd" style="width: 120px;">Сумма USD</th>
						<th class="th-party-type" style="width: 120px;">Party Type</th>
						<th class="th-party" style="width: 140px;">Party</th>
						<th class="th-date" style="width: 130px;">Дата</th>
						<th style="width: 40px;"></th>
					</tr>
				</thead>
				<tbody id="custom-table-body">
				</tbody>
			</table>
			<button class="btn btn-default btn-sm btn-add-row">
				<i class="fa fa-plus"></i> Add Row
			</button>
		</div>
	`;

	container.html(html);

	// Render existing rows
	items_data.forEach((item, idx) => {
		add_table_row(frm, idx, item);
	});

	// Add row button
	container.find('.btn-add-row').on('click', function() {
		let new_item = {
			izoh: '',
			podrazdilenie: '',
			rasxod_podochot: '',
			cost_center: '',
			category: '',
			talli_type: '',
			employee_group: '',
			employee: '',
			paid_amount_uzs: 0,
			paid_amount_usd: 0,
			party_type: '',
			party: '',
			date: ''
		};
		items_data.push(new_item);
		add_table_row(frm, items_data.length - 1, new_item);
		save_items_data(frm);
	});
}

function add_table_row(frm, idx, item) {
	let tbody = frm.fields_dict.custom_items_html.$wrapper.find('#custom-table-body');
	let $table = frm.fields_dict.custom_items_html.$wrapper.find('.custom-items-table');

	let is_rasxod = item.rasxod_podochot === 'Расход';
	let is_podochot = item.rasxod_podochot === 'Подотчет';
	let type_selected = is_rasxod || is_podochot;
	
	let mode_selected = frm.doc.mode_of_payment ? true : false;
	let usd_mode = is_usd_mode(frm);
	let uzs_mode = is_uzs_cash_mode(frm);
	let transfer_mode = is_uzs_transfer_mode(frm);
	
	// Party required only for Rasxod + Perechislenie UZS
	let party_required = is_rasxod && transfer_mode;
	
	// Date: required for Rasxod
	let date_required = is_rasxod;

	// Visibility based on type selection
	let show_cost_center = is_rasxod;
	let show_category = is_rasxod;
	let show_sektor = is_podochot;
	let show_employee = is_podochot;
	let show_party_type = is_rasxod;
	let show_party = is_rasxod;
	let show_date = type_selected;
	
	// Summa visibility based on mode of payment
	let show_uzs = mode_selected && (uzs_mode || transfer_mode);
	let show_usd = mode_selected; // USD always shown when mode selected
	let usd_readonly = uzs_mode || transfer_mode;

	// Update header visibility
	$table.find('.th-cost-center').toggle(show_cost_center);
	$table.find('.th-category').toggle(show_category);
	$table.find('.th-sektor').toggle(show_sektor);
	$table.find('.th-employee').toggle(show_employee);
	$table.find('.th-uzs').toggle(show_uzs);
	$table.find('.th-usd').toggle(show_usd);
	$table.find('.th-party-type').toggle(show_party_type);
	$table.find('.th-party').toggle(show_party);
	$table.find('.th-date').toggle(show_date);

	let row_html = `
		<tr data-idx="${idx}">
			<td class="row-idx">${idx + 1}</td>
			<td><textarea class="item-izoh">${item.izoh || ''}</textarea></td>
			<td>
				<select class="item-podrazdilenie">
					<option value="">-</option>
				</select>
			</td>
			<td>
				<select class="item-rasxod-podochot">
					<option value="">-</option>
					<option value="Расход" ${item.rasxod_podochot === 'Расход' ? 'selected' : ''}>Расход</option>
					<option value="Подотчет" ${item.rasxod_podochot === 'Подотчет' ? 'selected' : ''}>Подотчет</option>
				</select>
			</td>
			<td class="td-cost-center" style="${!show_cost_center ? 'display:none;' : ''}">
				<select class="item-cost-center">
					<option value="">-</option>
				</select>
			</td>
			<td class="td-category" style="${!show_category ? 'display:none;' : ''}">
				<select class="item-category">
					<option value="">-</option>
				</select>
			</td>
			<td class="td-sektor" style="${!show_sektor ? 'display:none;' : ''}">
				<select class="item-employee-group">
					<option value="">-</option>
				</select>
			</td>
			<td class="td-employee" style="${!show_employee ? 'display:none;' : ''}">
				<select class="item-employee">
					<option value="">-</option>
				</select>
			</td>
			<td class="td-uzs" style="${!show_uzs ? 'display:none;' : ''}">
				<input type="number" class="item-paid-amount-uzs" value="${item.paid_amount_uzs || 0}">
			</td>
			<td class="td-usd" style="${!show_usd ? 'display:none;' : ''}">
				<input type="number" class="item-paid-amount-usd" value="${item.paid_amount_usd || 0}" ${usd_readonly ? 'readonly' : ''}>
			</td>
			<td class="td-party-type" style="${!show_party_type ? 'display:none;' : ''}">
				<select class="item-party-type ${party_required ? 'required-field' : ''}">
					<option value="">-</option>
					<option value="Employee" ${item.party_type === 'Employee' ? 'selected' : ''}>Employee</option>
					<option value="Customer" ${item.party_type === 'Customer' ? 'selected' : ''}>Customer</option>
					<option value="Shareholder" ${item.party_type === 'Shareholder' ? 'selected' : ''}>Shareholder</option>
					<option value="Supplier" ${item.party_type === 'Supplier' ? 'selected' : ''}>Supplier</option>
				</select>
			</td>
			<td class="td-party" style="${!show_party ? 'display:none;' : ''}">
				<select class="item-party ${party_required ? 'required-field' : ''}">
					<option value="">-</option>
				</select>
			</td>
			<td class="td-date" style="${!show_date ? 'display:none;' : ''}">
				<input type="date" class="item-date ${date_required ? 'required-field' : ''}" value="${item.date || ''}">
			</td>
			<td class="delete-cell"><span class="btn-delete-row" title="Delete Row">×</span></td>
		</tr>
	`;

	tbody.append(row_html);

	let $row = tbody.find(`tr[data-idx="${idx}"]`);

	// Load Podrazdelenie options
	load_podrazdelenie_options($row, item.podrazdilenie);
	
	// Load Cost Center options if visible
	if (show_cost_center) {
		load_cost_center_options($row, item.cost_center);
		if (item.cost_center) {
			load_categories($row, item.cost_center, item.category);
		}
	}
	
	// Load Employee Group (Sektor) options if visible
	if (show_sektor) {
		load_employee_group_options($row, item.employee_group);
		if (item.employee_group) {
			load_employee_options($row, item.employee_group, item.employee);
		}
	}
	
	// Load Party options if visible and party_type is selected
	if (show_party && item.party_type) {
		load_party_options($row, item.party_type, item.party);
	}

	// Field change handlers
	$row.find('.item-izoh').on('change', function() {
		items_data[idx].izoh = $(this).val();
		save_items_data(frm);
	});

	$row.find('.item-podrazdilenie').on('change', function() {
		items_data[idx].podrazdilenie = $(this).val();
		save_items_data(frm);
	});

	$row.find('.item-rasxod-podochot').on('change', function() {
		items_data[idx].rasxod_podochot = $(this).val();
		// Clear conditional fields
		items_data[idx].cost_center = '';
		items_data[idx].category = '';
		items_data[idx].talli_type = '';
		items_data[idx].employee_group = '';
		items_data[idx].employee = '';
		items_data[idx].party_type = '';
		items_data[idx].party = '';
		items_data[idx].date = '';
		save_items_data(frm);
		refresh_custom_table(frm);
	});

	$row.find('.item-cost-center').on('change', function() {
		let cost_center = $(this).val();
		items_data[idx].cost_center = cost_center;
		items_data[idx].category = '';
		items_data[idx].talli_type = '';
		save_items_data(frm);

		if (cost_center) {
			load_categories($row, cost_center);
		}
	});

	$row.find('.item-category').on('change', function() {
		items_data[idx].category = $(this).val();
		save_items_data(frm);

		// Get talli_type
		if (items_data[idx].cost_center && items_data[idx].category) {
			get_talli_type(items_data[idx].cost_center, items_data[idx].category, idx);
		}
	});

	$row.find('.item-employee-group').on('change', function() {
		let employee_group = $(this).val();
		items_data[idx].employee_group = employee_group;
		items_data[idx].employee = '';
		save_items_data(frm);
		
		// Load employees for this group
		if (employee_group) {
			load_employee_options($row, employee_group, '');
		} else {
			$row.find('.item-employee').empty().append('<option value="">-</option>');
		}
	});

	$row.find('.item-employee').on('change', function() {
		items_data[idx].employee = $(this).val();
		save_items_data(frm);
	});

	$row.find('.item-paid-amount-uzs').on('change', function() {
		let uzs = parseFloat($(this).val()) || 0;
		items_data[idx].paid_amount_uzs = uzs;

		// UZS mode: convert to USD
		if (is_uzs_cash_mode(frm) && frm.doc.currency_exchange_rate) {
			items_data[idx].paid_amount_usd = uzs / frm.doc.currency_exchange_rate;
			$row.find('.item-paid-amount-usd').val(items_data[idx].paid_amount_usd.toFixed(2));
		}
		save_items_data(frm);
	});

	$row.find('.item-paid-amount-usd').on('change', function() {
		let usd = parseFloat($(this).val()) || 0;
		items_data[idx].paid_amount_usd = usd;
		// USD mode: no conversion needed
		save_items_data(frm);
	});

	$row.find('.item-party-type').on('change', function() {
		let party_type = $(this).val();
		items_data[idx].party_type = party_type;
		items_data[idx].party = '';
		save_items_data(frm);
		
		// Load party options
		if (party_type) {
			load_party_options($row, party_type, '');
		} else {
			$row.find('.item-party').empty().append('<option value="">-</option>');
		}
	});

	$row.find('.item-party').on('change', function() {
		items_data[idx].party = $(this).val();
		save_items_data(frm);
	});

	$row.find('.item-date').on('change', function() {
		items_data[idx].date = $(this).val();
		save_items_data(frm);
	});

	$row.find('.btn-delete-row').on('click', function() {
		if (confirm('Delete this row?')) {
			items_data.splice(idx, 1);
			save_items_data(frm);
			refresh_custom_table(frm);
		}
	});
}

function refresh_custom_table(frm) {
	render_custom_table(frm);
}

// Load Podrazdelenie options
function load_podrazdelenie_options($row, selected_value) {
	frappe.call({
		method: 'frappe.client.get_list',
		args: {
			doctype: 'Podrazdelenie',
			fields: ['name', 'podrazdelenie_name'],
			limit_page_length: 0
		},
		callback: function(r) {
			if (r.message) {
				let $select = $row.find('.item-podrazdilenie');
				$select.empty();
				$select.append('<option value="">-</option>');
				r.message.forEach(function(item) {
					let display = item.podrazdelenie_name || item.name;
					let selected = item.name === selected_value ? 'selected' : '';
					$select.append(`<option value="${item.name}" ${selected}>${display}</option>`);
				});
			}
		}
	});
}

// Load Custom Cost Center options
function load_cost_center_options($row, selected_value) {
	frappe.call({
		method: 'frappe.client.get_list',
		args: {
			doctype: 'Custom Cost Center',
			fields: ['name', 'cost_center'],
			limit_page_length: 0
		},
		callback: function(r) {
			if (r.message) {
				let $select = $row.find('.item-cost-center');
				$select.empty();
				$select.append('<option value="">-</option>');
				r.message.forEach(function(item) {
					let selected = item.name === selected_value ? 'selected' : '';
					$select.append(`<option value="${item.name}" ${selected}>${item.name}</option>`);
				});
			}
		}
	});
}

// Load Employee Group (Sektor) options
function load_employee_group_options($row, selected_value) {
	frappe.call({
		method: 'frappe.client.get_list',
		args: {
			doctype: 'Employee Group',
			fields: ['name'],
			limit_page_length: 0
		},
		callback: function(r) {
			if (r.message) {
				let $select = $row.find('.item-employee-group');
				$select.empty();
				$select.append('<option value="">-</option>');
				r.message.forEach(function(item) {
					let selected = item.name === selected_value ? 'selected' : '';
					$select.append(`<option value="${item.name}" ${selected}>${item.name}</option>`);
				});
			}
		}
	});
}

// Load Employee options filtered by Employee Group
function load_employee_options($row, employee_group, selected_value) {
	// Use whitelisted API to get employees
	frappe.call({
		method: 'akfa_accounting.akfa_accounting.doctype.kassa_rasxod.kassa_rasxod.get_employees_by_group',
		args: {
			employee_group: employee_group
		},
		callback: function(r) {
			let $select = $row.find('.item-employee');
			$select.empty();
			$select.append('<option value="">-</option>');
			if (r.message && r.message.length > 0) {
				r.message.forEach(function(item) {
					let display = item.employee_name ? `${item.employee} - ${item.employee_name}` : item.employee;
					let selected = item.employee === selected_value ? 'selected' : '';
					$select.append(`<option value="${item.employee}" ${selected}>${display}</option>`);
				});
			}
		}
	});
}

// Load Party options based on Party Type
function load_party_options($row, party_type, selected_value) {
	frappe.call({
		method: 'frappe.client.get_list',
		args: {
			doctype: party_type,
			fields: ['name'],
			limit_page_length: 0
		},
		callback: function(r) {
			if (r.message) {
				let $select = $row.find('.item-party');
				$select.empty();
				$select.append('<option value="">-</option>');
				r.message.forEach(function(item) {
					let selected = item.name === selected_value ? 'selected' : '';
					$select.append(`<option value="${item.name}" ${selected}>${item.name}</option>`);
				});
			}
		}
	});
}

function load_categories($row, cost_center, selected_category) {
	frappe.call({
		method: 'frappe.client.get',
		args: {
			doctype: 'Custom Cost Center',
			name: cost_center
		},
		callback: function(r) {
			if (r.message && r.message.categories) {
				let $select = $row.find('.item-category');
				$select.empty();
				$select.append('<option value="">-</option>');

				r.message.categories.forEach(function(cat) {
					let selected = cat.category_name === selected_category ? 'selected' : '';
					$select.append(`<option value="${cat.category_name}" ${selected}>${cat.category_name}</option>`);
				});
			}
		}
	});
}

function get_talli_type(cost_center, category, idx) {
	frappe.call({
		method: 'frappe.client.get',
		args: {
			doctype: 'Custom Cost Center',
			name: cost_center
		},
		callback: function(r) {
			if (r.message && r.message.categories) {
				let cat = r.message.categories.find(d => d.category_name === category);
				if (cat && cat.talli_type) {
					items_data[idx].talli_type = cat.talli_type;
				}
			}
		}
	});
}

function recalculate_all_amounts(frm) {
	// Only recalculate when in UZS mode
	if (is_uzs_cash_mode(frm) && frm.doc.currency_exchange_rate) {
		items_data.forEach(function(item) {
			if (item.paid_amount_uzs) {
				item.paid_amount_usd = item.paid_amount_uzs / frm.doc.currency_exchange_rate;
			}
		});
		save_items_data(frm);
		refresh_custom_table(frm);
	}
}

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
