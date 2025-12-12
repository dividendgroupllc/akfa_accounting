frappe.ui.form.on('Custom Cost Center', {
	setup: function(frm) {
		// Filter category_name to show only child accounts of 5200 - Indirect Expenses - A
		frm.set_query('category_name', 'categories', function() {
			return {
				filters: {
					parent_account: '5200 - Indirect Expenses - A',
					is_group: 0
				}
			};
		});
	}
});
