// Kassa Rasxod — per-row event handlers (change/click/upload)
(function () {
	const ns = window.akfa_kr = window.akfa_kr || {};

	ns.setup_row_handlers = function (frm, $row, idx) {
		$row.find('.item-izoh').on('change', function () {
			ns.items_data[idx].izoh = $(this).val();
			ns.save_items_data(frm);
		});

		$row.find('.item-podrazdilenie').on('change', function () {
			ns.items_data[idx].podrazdilenie = $(this).val();
			ns.save_items_data(frm);
		});

		$row.find('.item-rasxod-podochot').on('change', function () {
			ns.items_data[idx].rasxod_podochot = $(this).val();
			// Clear conditional fields
			Object.assign(ns.items_data[idx], {
				cost_center: '',
				category: '',
				talli_type: '',
				employee_group: '',
				employee: '',
				party_type: '',
				party: '',
				party_type_2: '',
				party_2: '',
				date: ''
			});
			ns.save_items_data(frm);
			ns.refresh_custom_table(frm);
		});

		$row.find('.item-cost-center').on('change', function () {
			let cost_center = $(this).val();
			ns.items_data[idx].cost_center = cost_center;
			ns.items_data[idx].category = '';
			ns.items_data[idx].talli_type = '';
			ns.save_items_data(frm);
			if (cost_center) {
				ns.load_categories($row, cost_center);
			}
		});

		$row.find('.item-category').on('change', function () {
			ns.items_data[idx].category = $(this).val();
			ns.save_items_data(frm);
		});

		$row.find('.item-employee-group').on('change', function () {
			let employee_group = $(this).val();
			ns.items_data[idx].employee_group = employee_group;
			ns.items_data[idx].employee = '';
			ns.save_items_data(frm);
			if (employee_group) {
				ns.load_employee_options($row, employee_group, '');
			} else {
				$row.find('.item-employee').empty().append('<option value="">-</option>');
			}
		});

		$row.find('.item-employee').on('change', function () {
			ns.items_data[idx].employee = $(this).val();
			ns.save_items_data(frm);
		});

		$row.find('.item-paid-amount-uzs').on('change', function () {
			let uzs = parseFloat($(this).val()) || 0;
			ns.items_data[idx].paid_amount_uzs = uzs;
			let row_rate = ns.items_data[idx].currency_exchange_rate || frm.doc.currency_exchange_rate;
			if (row_rate) {
				ns.items_data[idx].paid_amount_usd = uzs / row_rate;
			}
			ns.save_items_data(frm);
		});

		$row.find('.item-paid-amount-usd').on('change', function () {
			let usd = parseFloat($(this).val()) || 0;
			ns.items_data[idx].paid_amount_usd = usd;
			ns.save_items_data(frm);
		});

		$row.find('.item-currency-exchange-rate').on('change', function () {
			let rate = parseFloat($(this).val()) || 0;
			ns.items_data[idx].currency_exchange_rate = rate;
			ns.items_data[idx]._kurs_overridden = true;
			if (!ns.is_usd_mode(frm) && rate && ns.items_data[idx].paid_amount_uzs) {
				ns.items_data[idx].paid_amount_usd = ns.items_data[idx].paid_amount_uzs / rate;
			}
			ns.save_items_data(frm);
			ns.refresh_custom_table(frm);
		});

		$row.find('.item-party-type').on('change', function () {
			let party_type = $(this).val();
			ns.items_data[idx].party_type = party_type;
			ns.items_data[idx].party = '';
			ns.save_items_data(frm);
			if (party_type) {
				ns.load_party_options($row, '.item-party', party_type, '');
			} else {
				$row.find('.item-party').empty().append('<option value="">-</option>');
			}
		});

		$row.find('.item-party').on('change', function () {
			ns.items_data[idx].party = $(this).val();
			ns.save_items_data(frm);
		});

		$row.find('.item-party-type-2').on('change', function () {
			let party_type = $(this).val();
			ns.items_data[idx].party_type_2 = party_type;
			ns.items_data[idx].party_2 = '';
			ns.save_items_data(frm);
			if (party_type) {
				ns.load_party_options($row, '.item-party-2', party_type, '');
			} else {
				$row.find('.item-party-2').empty().append('<option value="">-</option>');
			}
		});

		$row.find('.item-party-2').on('change', function () {
			ns.items_data[idx].party_2 = $(this).val();
			ns.save_items_data(frm);
		});

		$row.find('.item-date').on('change', function () {
			ns.items_data[idx].date = $(this).val();
			ns.save_items_data(frm);
		});

		$row.find('.btn-delete-row').on('click', function () {
			if (confirm('Delete this row?')) {
				ns.items_data.splice(idx, 1);
				ns.save_items_data(frm);
				ns.refresh_custom_table(frm);
			}
		});

		// Upload file handler
		$row.find('.item-upload-btn').on('click', function () {
			let $btn = $(this);
			let existing_file = $btn.data('file');

			if (existing_file) {
				frappe.msgprint({
					title: __('File Attached'),
					message: `<a href="${existing_file}" target="_blank">${__('View File')}</a><br><br>
						<button class="btn btn-danger btn-sm remove-file-btn">${__('Remove File')}</button>`,
					primary_action: {
						label: __('Close'),
						action: function () {
							frappe.msg_dialog.hide();
						}
					}
				});

				$(document).on('click', '.remove-file-btn', function () {
					ns.items_data[idx].upload_file = '';
					$btn.data('file', '');
					$btn.find('i').removeClass('fa-file').addClass('fa-upload');
					ns.save_items_data(frm);
					frappe.msg_dialog.hide();
				});
			} else {
				$row.find('.item-upload-file').click();
			}
		});

		$row.find('.item-upload-file').on('change', function (e) {
			let file = e.target.files[0];
			if (file) {
				let $btn = $row.find('.item-upload-btn');
				frappe.upload_handler({
					files: [file],
					doctype: frm.doctype,
					docname: frm.docname || 'New ' + frm.doctype,
					folder: 'Home/Attachments',
					is_private: 1,
					callback: function (attachment) {
						ns.items_data[idx].upload_file = attachment.file_url;
						$btn.data('file', attachment.file_url);
						$btn.find('i').removeClass('fa-upload').addClass('fa-file');
						ns.save_items_data(frm);
						frappe.show_alert({ message: __('File uploaded successfully'), indicator: 'green' });
					}
				});
			}
		});
	};
})();
