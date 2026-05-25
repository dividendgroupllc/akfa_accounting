// Kassa Rasxod — table rendering: container, rows, header, column resizers
(function () {
	const ns = window.akfa_kr = window.akfa_kr || {};

	ns.render_custom_table = function (frm) {
		let container = frm.fields_dict.custom_items_html.$wrapper;
		container.empty();

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
					font-size: 14px;
					border: 1px solid #d1d8dd;
					border-radius: 4px;
					table-layout: fixed;
				}
				.custom-items-table th {
					position: relative;
					background: linear-gradient(to bottom, #fafbfc, #f1f3f5);
					border-bottom: 2px solid #d1d8dd;
					border-right: 1px solid #e8e8e8;
					padding: 12px 10px;
					text-align: center;
					font-weight: 600;
					color: #333;
					font-size: 13px;
					white-space: nowrap;
					overflow: hidden;
					text-overflow: ellipsis;
				}
				.custom-items-table th:last-child {
					border-right: none;
				}
				.col-resizer {
					position: absolute;
					top: 0;
					right: 0;
					width: 6px;
					height: 100%;
					cursor: col-resize;
					user-select: none;
					z-index: 5;
				}
				.col-resizer:hover,
				.col-resizer.resizing {
					background: #80bdff;
				}
				body.col-resizing,
				body.col-resizing * {
					cursor: col-resize !important;
					user-select: none !important;
				}
				.custom-items-table td {
					border-bottom: 1px solid #e8e8e8;
					border-right: 1px solid #e8e8e8;
					padding: 8px 10px;
					vertical-align: middle;
					background: #fff;
					overflow: hidden;
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
					min-height: 36px;
					border: 1px solid #d1d8dd;
					border-radius: 3px;
					padding: 8px 12px;
					font-size: 14px;
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
					min-height: 50px;
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
						</tr>
					</thead>
					<tbody id="custom-table-body"></tbody>
				</table>
				<button class="btn btn-default btn-sm btn-add-row">
					<i class="fa fa-plus"></i> Add Row
				</button>
			</div>
		`;

		container.html(html);
		ns.attach_column_resizers(frm);

		// Render existing rows
		ns.items_data.forEach((item, idx) => {
			ns.add_table_row(frm, idx, item);
		});

		// Add row button
		container.find('.btn-add-row').on('click', function () {
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
				currency_exchange_rate: frm.doc.currency_exchange_rate || 0,
				_kurs_overridden: false,
				party_type: '',
				party: '',
				party_type_2: '',
				party_2: '',
				date: '',
				upload_file: ''
			};
			ns.items_data.push(new_item);
			ns.add_table_row(frm, ns.items_data.length - 1, new_item);
			ns.save_items_data(frm);
		});
	};

	ns.add_table_row = function (frm, idx, item) {
		let tbody = frm.fields_dict.custom_items_html.$wrapper.find('#custom-table-body');

		let tip = item.rasxod_podochot;
		let is_rasxod = tip === ns.TIP_RASXOD;
		let is_podochot_prixod = tip === ns.TIP_PODOCHOT_PRIXOD;
		let is_podochot_rasxod = tip === ns.TIP_PODOCHOT_RASXOD;
		let is_koplashga = tip === ns.TIP_KOPLASHGA;
		let is_podochot_type = is_podochot_prixod || is_podochot_rasxod;

		let mode_selected = frm.doc.mode_of_payment ? true : false;
		let usd_mode = ns.is_usd_mode(frm);

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
					<option value="${ns.TIP_RASXOD}" ${tip === ns.TIP_RASXOD ? 'selected' : ''}>Расход</option>
					<option value="${ns.TIP_PODOCHOT_PRIXOD}" ${tip === ns.TIP_PODOCHOT_PRIXOD ? 'selected' : ''}>Подотчет приход</option>
					<option value="${ns.TIP_PODOCHOT_RASXOD}" ${tip === ns.TIP_PODOCHOT_RASXOD ? 'selected' : ''}>Подотчет расход</option>
					<option value="${ns.TIP_KOPLASHGA}" ${tip === ns.TIP_KOPLASHGA ? 'selected' : ''}>Коплашга</option>
				</select>
			</td>`;

		if (is_rasxod) {
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

			if (usd_mode) {
				row_html += `
				<td>
					<input type="number" class="item-paid-amount-usd" value="${item.paid_amount_usd || 0}" step="0.01">
				</td>`;
			} else if (mode_selected) {
				row_html += `
				<td>
					<input type="number" class="item-paid-amount-uzs" value="${item.paid_amount_uzs || 0}" step="0.01">
				</td>
				<td>
					<input type="number" class="item-currency-exchange-rate" value="${item.currency_exchange_rate || frm.doc.currency_exchange_rate || 0}" step="0.01">
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

			if (usd_mode) {
				row_html += `
				<td>
					<input type="number" class="item-paid-amount-usd" value="${item.paid_amount_usd || 0}" step="0.01">
				</td>`;
			} else if (mode_selected) {
				row_html += `
				<td>
					<input type="number" class="item-paid-amount-uzs" value="${item.paid_amount_uzs || 0}" step="0.01">
				</td>
				<td>
					<input type="number" class="item-currency-exchange-rate" value="${item.currency_exchange_rate || frm.doc.currency_exchange_rate || 0}" step="0.01">
				</td>`;
			}

			row_html += `
			<td>
				<button type="button" class="btn btn-xs btn-default item-upload-btn" data-file="${item.upload_file || ''}">
					<i class="fa ${item.upload_file ? 'fa-file' : 'fa-upload'}"></i>
				</button>
				<input type="file" class="item-upload-file" style="display:none;">
			</td>`;
		} else if (is_koplashga) {
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

			if (usd_mode) {
				row_html += `
				<td>
					<input type="number" class="item-paid-amount-usd" value="${item.paid_amount_usd || 0}" step="0.01">
				</td>`;
			} else if (mode_selected) {
				row_html += `
				<td>
					<input type="number" class="item-paid-amount-uzs" value="${item.paid_amount_uzs || 0}" step="0.01">
				</td>
				<td>
					<input type="number" class="item-currency-exchange-rate" value="${item.currency_exchange_rate || frm.doc.currency_exchange_rate || 0}" step="0.01">
				</td>`;
			}

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

		ns.load_podrazdelenie_options($row, item.podrazdilenie);

		if (is_rasxod) {
			ns.load_cost_center_options($row, item.cost_center);
			if (item.cost_center) {
				ns.load_categories($row, item.cost_center, item.category);
			}
			if (item.party_type) {
				ns.load_party_options($row, '.item-party', item.party_type, item.party);
			}
		} else if (is_podochot_type) {
			ns.load_employee_group_options($row, item.employee_group);
			if (item.employee_group) {
				ns.load_employee_options($row, item.employee_group, item.employee);
			}
		} else if (is_koplashga) {
			if (item.party_type) {
				ns.load_party_options($row, '.item-party', item.party_type, item.party);
			}
			if (item.party_type_2) {
				ns.load_party_options($row, '.item-party-2', item.party_type_2, item.party_2);
			}
		}

		ns.setup_row_handlers(frm, $row, idx);
		ns.update_table_header(frm, tip);
	};

	ns.update_table_header = function (frm, tip) {
		let $header = frm.fields_dict.custom_items_html.$wrapper.find('#table-header');
		$header.find('.dynamic-col').remove();

		let mode_selected = frm.doc.mode_of_payment ? true : false;
		let usd_mode = ns.is_usd_mode(frm);
		let summa_label = usd_mode ? 'Сумма USD' : 'Сумма UZS';

		let header_html = '';
		let kurs_th = (mode_selected && !usd_mode) ? `<th class="dynamic-col" style="width: 100px;">Курс</th>` : '';

		if (tip === ns.TIP_RASXOD) {
			header_html = `
				<th class="dynamic-col" style="width: 150px;">Счёт</th>
				<th class="dynamic-col" style="width: 130px;">Тип 1</th>`;
			if (mode_selected) {
				header_html += `<th class="dynamic-col" style="width: 120px;">${summa_label}</th>${kurs_th}`;
			}
			header_html += `
				<th class="dynamic-col" style="width: 120px;">Party Type</th>
				<th class="dynamic-col" style="width: 140px;">Party</th>
				<th class="dynamic-col" style="width: 130px;">Дата *</th>
				<th class="dynamic-col" style="width: 50px;">File</th>`;
		} else if (tip === ns.TIP_PODOCHOT_PRIXOD || tip === ns.TIP_PODOCHOT_RASXOD) {
			header_html = `
				<th class="dynamic-col" style="width: 140px;">Сектор</th>
				<th class="dynamic-col" style="width: 150px;">Сотрудник</th>`;
			if (mode_selected) {
				header_html += `<th class="dynamic-col" style="width: 120px;">${summa_label}</th>${kurs_th}`;
			}
			header_html += `<th class="dynamic-col" style="width: 50px;">File</th>`;
		} else if (tip === ns.TIP_KOPLASHGA) {
			header_html = `
				<th class="dynamic-col" style="width: 120px;">Party Type</th>
				<th class="dynamic-col" style="width: 140px;">Party</th>`;
			if (mode_selected) {
				header_html += `<th class="dynamic-col" style="width: 120px;">${summa_label}</th>${kurs_th}`;
			}
			header_html += `
				<th class="dynamic-col" style="width: 120px;">Party Type 2</th>
				<th class="dynamic-col" style="width: 140px;">Party 2</th>
				<th class="dynamic-col" style="width: 50px;">File</th>`;
		}

		header_html += `<th class="dynamic-col" style="width: 40px;"></th>`;

		$header.append(header_html);
		ns.attach_column_resizers(frm);
	};

	ns.attach_column_resizers = function (frm) {
		let $table = frm.fields_dict.custom_items_html.$wrapper.find('.custom-items-table');
		let $ths = $table.find('thead th');

		$ths.each(function (col_idx) {
			let $th = $(this);
			// Skip last col (delete) and avoid duplicates
			if (col_idx === $ths.length - 1 || $th.find('.col-resizer').length) return;

			let $resizer = $(`<div class="col-resizer"></div>`);
			$th.append($resizer);

			$resizer.on('mousedown', function (e) {
				e.preventDefault();
				e.stopPropagation();
				let start_x = e.pageX;
				let start_w = $th.outerWidth();
				$resizer.addClass('resizing');
				$('body').addClass('col-resizing');

				function on_move(ev) {
					let new_w = Math.max(40, start_w + (ev.pageX - start_x));
					$th.css('width', new_w + 'px');
				}
				function on_up() {
					$(document).off('mousemove', on_move).off('mouseup', on_up);
					$resizer.removeClass('resizing');
					$('body').removeClass('col-resizing');
				}
				$(document).on('mousemove', on_move).on('mouseup', on_up);
			});
		});
	};
})();
