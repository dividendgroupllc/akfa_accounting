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
		get_account_balance(frm);
		refresh_custom_table(frm);
	},

	currency_exchange_rate: function(frm) {
		recalculate_all_amounts(frm);
	}
});

let items_data = [];

// Tip types
const TIP_RASXOD = 'Расход';
const TIP_PODOCHOT_PRIXOD = 'Подотчет приход';
const TIP_PODOCHOT_RASXOD = 'Подотчет расход';
const TIP_KOPLASHGA = 'Коплашга';

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

function load_custom_table(frm) {
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
	calculate_totals(frm);
}

function save_items_data(frm) {
	frm.set_value('items_data', JSON.stringify(items_data));
	calculate_totals(frm);
}

function render_custom_table(frm) {
	let container = frm.fields_dict.custom_items_html.$wrapper;
	container.empty();

	let mode_selected = frm.doc.mode_of_payment ? true : false;
	let usd_mode = is_usd_mode(frm);

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
					<tr id="table-header">
						<th style="width: 40px;">#</th>
						<th style="width: 150px;">Изох</th>
						<th style="width: 140px;">Подразделение</th>
						<th style="width: 130px;">Тип</th>
						<!-- Dynamic columns will be managed per row -->
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
			party_type_2: '',
			party_2: '',
			date: '',
			upload_file: ''
		};
		items_data.push(new_item);
		add_table_row(frm, items_data.length - 1, new_item);
		save_items_data(frm);
	});
}

function add_table_row(frm, idx, item) {
	let tbody = frm.fields_dict.custom_items_html.$wrapper.find('#custom-table-body');

	let tip = item.rasxod_podochot;
	let is_rasxod = tip === TIP_RASXOD;
	let is_podochot_prixod = tip === TIP_PODOCHOT_PRIXOD;
	let is_podochot_rasxod = tip === TIP_PODOCHOT_RASXOD;
	let is_koplashga = tip === TIP_KOPLASHGA;
	let is_podochot_type = is_podochot_prixod || is_podochot_rasxod;
	
	let mode_selected = frm.doc.mode_of_payment ? true : false;
	let usd_mode = is_usd_mode(frm);
	let transfer_mode = is_uzs_transfer_mode(frm);

	// Build row HTML dynamically based on type
	let row_html = `<tr data-idx="${idx}">
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
				<option value="${TIP_RASXOD}" ${tip === TIP_RASXOD ? 'selected' : ''}>Расход</option>
				<option value="${TIP_PODOCHOT_PRIXOD}" ${tip === TIP_PODOCHOT_PRIXOD ? 'selected' : ''}>Подотчет приход</option>
				<option value="${TIP_PODOCHOT_RASXOD}" ${tip === TIP_PODOCHOT_RASXOD ? 'selected' : ''}>Подотчет расход</option>
				<option value="${TIP_KOPLASHGA}" ${tip === TIP_KOPLASHGA ? 'selected' : ''}>Коплашга</option>
			</select>
		</td>`;

	// Add columns based on type
	if (is_rasxod) {
		// Расход: Cost Center, Tip 1, Summa, Party Type, Party, Date
		row_html += `
		<td>
			<select class="item-cost-center">
				<option value="">-</option>
			</select>
		</td>
		<td>
			<select class="item-category">
				<option value="">-</option>
			</select>
		</td>`;
		
		// Add Summa field for Rasxod after Tip 1
		if (usd_mode) {
			row_html += `
			<td>
				<input type="number" class="item-paid-amount-usd" value="${item.paid_amount_usd || 0}" step="0.01">
			</td>`;
		} else if (mode_selected) {
			row_html += `
			<td>
				<input type="number" class="item-paid-amount-uzs" value="${item.paid_amount_uzs || 0}" step="0.01">
			</td>`;
		}
		
		row_html += `
		<td>
			<select class="item-party-type">
				<option value="">-</option>
				<option value="Employee" ${item.party_type === 'Employee' ? 'selected' : ''}>Employee</option>
				<option value="Customer" ${item.party_type === 'Customer' ? 'selected' : ''}>Customer</option>
				<option value="Shareholder" ${item.party_type === 'Shareholder' ? 'selected' : ''}>Shareholder</option>
				<option value="Supplier" ${item.party_type === 'Supplier' ? 'selected' : ''}>Supplier</option>
			</select>
		</td>
		<td>
			<select class="item-party">
				<option value="">-</option>
			</select>
		</td>
		<td>
			<input type="date" class="item-date required-field" value="${item.date || ''}" required>
		</td>
		<td>
			<button type="button" class="btn btn-xs btn-default item-upload-btn" data-file="${item.upload_file || ''}">
				<i class="fa ${item.upload_file ? 'fa-file' : 'fa-upload'}"></i>
			</button>
			<input type="file" class="item-upload-file" style="display:none;">
		</td>`;
	} else if (is_podochot_type) {
		// Подотчет приход/расход: Sektor, Sotrudnik, Summa
		row_html += `
		<td>
			<select class="item-employee-group">
				<option value="">-</option>
			</select>
		</td>
		<td>
			<select class="item-employee">
				<option value="">-</option>
			</select>
		</td>`;
		
		// Add Summa field for Podochot types
		if (usd_mode) {
			row_html += `
			<td>
				<input type="number" class="item-paid-amount-usd" value="${item.paid_amount_usd || 0}" step="0.01">
			</td>`;
		} else if (mode_selected) {
			row_html += `
			<td>
				<input type="number" class="item-paid-amount-uzs" value="${item.paid_amount_uzs || 0}" step="0.01">
			</td>`;
		}
		
		// Upload file for Podochot
		row_html += `
		<td>
			<button type="button" class="btn btn-xs btn-default item-upload-btn" data-file="${item.upload_file || ''}">
				<i class="fa ${item.upload_file ? 'fa-file' : 'fa-upload'}"></i>
			</button>
			<input type="file" class="item-upload-file" style="display:none;">
		</td>`;
	} else if (is_koplashga) {
		// Коплашга: Party Type 1, Party 1, Summa, Party Type 2, Party 2
		row_html += `
		<td>
			<select class="item-party-type">
				<option value="">-</option>
				<option value="Employee" ${item.party_type === 'Employee' ? 'selected' : ''}>Employee</option>
				<option value="Customer" ${item.party_type === 'Customer' ? 'selected' : ''}>Customer</option>
				<option value="Shareholder" ${item.party_type === 'Shareholder' ? 'selected' : ''}>Shareholder</option>
				<option value="Supplier" ${item.party_type === 'Supplier' ? 'selected' : ''}>Supplier</option>
			</select>
		</td>
		<td>
			<select class="item-party">
				<option value="">-</option>
			</select>
		</td>`;
		
		// Add Summa field for Koplashga
		if (usd_mode) {
			row_html += `
			<td>
				<input type="number" class="item-paid-amount-usd" value="${item.paid_amount_usd || 0}" step="0.01">
			</td>`;
		} else if (mode_selected) {
			row_html += `
			<td>
				<input type="number" class="item-paid-amount-uzs" value="${item.paid_amount_uzs || 0}" step="0.01">
			</td>`;
		}
		
		// Add Party Type 2 and Party 2 for Koplashga AFTER summa
		row_html += `
		<td>
			<select class="item-party-type-2">
				<option value="">-</option>
				<option value="Employee" ${item.party_type_2 === 'Employee' ? 'selected' : ''}>Employee</option>
				<option value="Customer" ${item.party_type_2 === 'Customer' ? 'selected' : ''}>Customer</option>
				<option value="Shareholder" ${item.party_type_2 === 'Shareholder' ? 'selected' : ''}>Shareholder</option>
				<option value="Supplier" ${item.party_type_2 === 'Supplier' ? 'selected' : ''}>Supplier</option>
			</select>
		</td>
		<td>
			<select class="item-party-2">
				<option value="">-</option>
			</select>
		</td>
		<td>
			<button type="button" class="btn btn-xs btn-default item-upload-btn" data-file="${item.upload_file || ''}">
				<i class="fa ${item.upload_file ? 'fa-file' : 'fa-upload'}"></i>
			</button>
			<input type="file" class="item-upload-file" style="display:none;">
		</td>`;
	}

	row_html += `<td class="delete-cell"><span class="btn-delete-row" title="Delete Row">×</span></td></tr>`;

	tbody.append(row_html);

	let $row = tbody.find(`tr[data-idx="${idx}"]`);

	// Load Podrazdelenie options
	load_podrazdelenie_options($row, item.podrazdilenie);

	// Load options based on type
	if (is_rasxod) {
		load_cost_center_options($row, item.cost_center);
		if (item.cost_center) {
			load_categories($row, item.cost_center, item.category);
		}
		if (item.party_type) {
			load_party_options($row, '.item-party', item.party_type, item.party);
		}
	} else if (is_podochot_type) {
		load_employee_group_options($row, item.employee_group);
		if (item.employee_group) {
			load_employee_options($row, item.employee_group, item.employee);
		}
	} else if (is_koplashga) {
		if (item.party_type) {
			load_party_options($row, '.item-party', item.party_type, item.party);
		}
		if (item.party_type_2) {
			load_party_options($row, '.item-party-2', item.party_type_2, item.party_2);
		}
	}

	// Event handlers
	setup_row_handlers(frm, $row, idx);

	// Update header to match current row structure
	update_table_header(frm, tip);
}

function update_table_header(frm, tip) {
	let $header = frm.fields_dict.custom_items_html.$wrapper.find('#table-header');
	
	// Remove old dynamic columns
	$header.find('.dynamic-col').remove();
	
	let mode_selected = frm.doc.mode_of_payment ? true : false;
	let usd_mode = is_usd_mode(frm);
	let summa_label = usd_mode ? 'Сумма USD' : 'Сумма UZS';

	let header_html = '';
	
	if (tip === TIP_RASXOD) {
		// Расход: Cost Center, Tip 1, Summa, Party Type, Party, Date, File
		header_html = `
			<th class="dynamic-col" style="width: 150px;">Cost Center</th>
			<th class="dynamic-col" style="width: 130px;">Тип 1</th>`;
		if (mode_selected) {
			header_html += `<th class="dynamic-col" style="width: 120px;">${summa_label}</th>`;
		}
		header_html += `
			<th class="dynamic-col" style="width: 120px;">Party Type</th>
			<th class="dynamic-col" style="width: 140px;">Party</th>
			<th class="dynamic-col" style="width: 130px;">Дата *</th>
			<th class="dynamic-col" style="width: 50px;">File</th>`;
	} else if (tip === TIP_PODOCHOT_PRIXOD || tip === TIP_PODOCHOT_RASXOD) {
		// Подотчет: Sektor, Sotrudnik, Summa, File
		header_html = `
			<th class="dynamic-col" style="width: 140px;">Сектор</th>
			<th class="dynamic-col" style="width: 150px;">Сотрудник</th>`;
		if (mode_selected) {
			header_html += `<th class="dynamic-col" style="width: 120px;">${summa_label}</th>`;
		}
		header_html += `<th class="dynamic-col" style="width: 50px;">File</th>`;
	} else if (tip === TIP_KOPLASHGA) {
		// Коплашга: Party Type, Party, Summa, Party Type 2, Party 2, File
		header_html = `
			<th class="dynamic-col" style="width: 120px;">Party Type</th>
			<th class="dynamic-col" style="width: 140px;">Party</th>`;
		if (mode_selected) {
			header_html += `<th class="dynamic-col" style="width: 120px;">${summa_label}</th>`;
		}
		header_html += `
			<th class="dynamic-col" style="width: 120px;">Party Type 2</th>
			<th class="dynamic-col" style="width: 140px;">Party 2</th>
			<th class="dynamic-col" style="width: 50px;">File</th>`;
	}

	// Add delete column
	header_html += `<th class="dynamic-col" style="width: 40px;"></th>`;
	
	$header.append(header_html);
}

function setup_row_handlers(frm, $row, idx) {
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
		items_data[idx].party_type_2 = '';
		items_data[idx].party_2 = '';
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

		if (items_data[idx].cost_center && items_data[idx].category) {
			get_talli_type(items_data[idx].cost_center, items_data[idx].category, idx);
		}
	});

	$row.find('.item-employee-group').on('change', function() {
		let employee_group = $(this).val();
		items_data[idx].employee_group = employee_group;
		items_data[idx].employee = '';
		save_items_data(frm);
		
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

		// Calculate USD automatically
		if (frm.doc.currency_exchange_rate) {
			items_data[idx].paid_amount_usd = uzs / frm.doc.currency_exchange_rate;
		}
		save_items_data(frm);
	});

	$row.find('.item-paid-amount-usd').on('change', function() {
		let usd = parseFloat($(this).val()) || 0;
		items_data[idx].paid_amount_usd = usd;
		save_items_data(frm);
	});

	$row.find('.item-party-type').on('change', function() {
		let party_type = $(this).val();
		items_data[idx].party_type = party_type;
		items_data[idx].party = '';
		save_items_data(frm);
		
		if (party_type) {
			load_party_options($row, '.item-party', party_type, '');
		} else {
			$row.find('.item-party').empty().append('<option value="">-</option>');
		}
	});

	$row.find('.item-party').on('change', function() {
		items_data[idx].party = $(this).val();
		save_items_data(frm);
	});

	// Party Type 2 and Party 2 for Koplashga
	$row.find('.item-party-type-2').on('change', function() {
		let party_type = $(this).val();
		items_data[idx].party_type_2 = party_type;
		items_data[idx].party_2 = '';
		save_items_data(frm);
		
		if (party_type) {
			load_party_options($row, '.item-party-2', party_type, '');
		} else {
			$row.find('.item-party-2').empty().append('<option value="">-</option>');
		}
	});

	$row.find('.item-party-2').on('change', function() {
		items_data[idx].party_2 = $(this).val();
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

	// Upload file handler
	$row.find('.item-upload-btn').on('click', function() {
		let $btn = $(this);
		let existing_file = $btn.data('file');
		
		if (existing_file) {
			// Show options: view or remove
			frappe.msgprint({
				title: __('File Attached'),
				message: `<a href="${existing_file}" target="_blank">${__('View File')}</a><br><br>
					<button class="btn btn-danger btn-sm remove-file-btn">${__('Remove File')}</button>`,
				primary_action: {
					label: __('Close'),
					action: function() {
						frappe.msg_dialog.hide();
					}
				}
			});
			
			$(document).on('click', '.remove-file-btn', function() {
				items_data[idx].upload_file = '';
				$btn.data('file', '');
				$btn.find('i').removeClass('fa-file').addClass('fa-upload');
				save_items_data(frm);
				frappe.msg_dialog.hide();
			});
		} else {
			$row.find('.item-upload-file').click();
		}
	});

	$row.find('.item-upload-file').on('change', function(e) {
		let file = e.target.files[0];
		if (file) {
			// Upload file using Frappe
			let $btn = $row.find('.item-upload-btn');
			
			frappe.upload_handler({
				files: [file],
				doctype: frm.doctype,
				docname: frm.docname || 'New ' + frm.doctype,
				folder: 'Home/Attachments',
				is_private: 1,
				callback: function(attachment) {
					items_data[idx].upload_file = attachment.file_url;
					$btn.data('file', attachment.file_url);
					$btn.find('i').removeClass('fa-upload').addClass('fa-file');
					save_items_data(frm);
					frappe.show_alert({message: __('File uploaded successfully'), indicator: 'green'});
				}
			});
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
function load_party_options($row, selector, party_type, selected_value) {
	frappe.call({
		method: 'frappe.client.get_list',
		args: {
			doctype: party_type,
			fields: ['name'],
			limit_page_length: 0
		},
		callback: function(r) {
			if (r.message) {
				let $select = $row.find(selector);
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
	if (!is_usd_mode(frm) && frm.doc.currency_exchange_rate) {
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

function get_account_balance(frm) {
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
		callback: function(r) {
			if (r.message !== undefined) {
				frm.set_value('balance', r.message);
				calculate_totals(frm);
			}
		}
	});
}

function calculate_totals(frm) {
	let total_amount = 0;
	let podochot_prixod_sum = 0;
	let koplashga_plus = 0;

	let usd_mode = is_usd_mode(frm);
	let exchange_rate = frm.doc.currency_exchange_rate || 1;

	items_data.forEach(function(item) {
		// Get amount in USD
		let summa_usd;
		if (usd_mode) {
			summa_usd = item.paid_amount_usd || 0;
		} else {
			// UZS mode - convert to USD
			let uzs_amount = item.paid_amount_uzs || 0;
			summa_usd = uzs_amount / exchange_rate;
		}
		
		if (item.rasxod_podochot === TIP_RASXOD) {
			// Rasxod: add to total if party_type and party are empty
			if (!item.party_type || !item.party) {
				total_amount += summa_usd;
			}
		} else if (item.rasxod_podochot === TIP_PODOCHOT_PRIXOD) {
			// Podochot prixod: add to balance (plus)
			podochot_prixod_sum += summa_usd;
		} else if (item.rasxod_podochot === TIP_PODOCHOT_RASXOD) {
			// Podochot rasxod: add to total amount
			total_amount += summa_usd;
		} else if (item.rasxod_podochot === TIP_KOPLASHGA) {
			// Koplashga logic:
			let has_party1 = item.party_type && item.party;
			let has_party2 = item.party_type_2 && item.party_2;
			
			if (has_party1 && has_party2) {
				// Both parties filled - no effect on balance
			} else if (has_party1 && !has_party2) {
				// Only first party - add to balance (pul keldi)
				koplashga_plus += summa_usd;
			} else if (!has_party1 && has_party2) {
				// Only second party - add to total amount (pul ketdi)
				total_amount += summa_usd;
			}
		}
	});

	// Set total_amount field (always in USD)
	frm.set_value('total_amount', total_amount);

	// Calculate qoldi: balance + podochot_prixod + koplashga_plus - total_amount
	let balance = frm.doc.balance || 0;
	let qoldi = balance + podochot_prixod_sum + koplashga_plus - total_amount;
	frm.set_value('qoldi', qoldi);
}
