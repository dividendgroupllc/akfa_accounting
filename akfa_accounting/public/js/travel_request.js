// Travel Request customizations
// Simplified - Trip Overview removed (handled by Mobile HR)

frappe.ui.form.on('Travel Request', {
	refresh(frm) {
		// Show Trip Master link if exists
		if (frm.doc.custom_trip_master) {
			frm.dashboard.add_indicator(
				__('Trip: {0}', [frm.doc.custom_trip_master]),
				'blue'
			);
		}
	}
});
