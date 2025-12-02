// Copyright (c) 2025, Asadbek and contributors
// For license information, please see license.txt

frappe.ui.form.on("Cash Distribution Entry", {
	refresh(frm) {
		// Add custom button to fetch payment entries
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Fetch Payment Entries"), function() {
				frm.trigger("fetch_payment_entries");
			});
		}

		// Show link to Journal Entries if exists
		if (frm.doc.journal_entry) {
			frm.add_custom_button(__("View Journal Entries"), function() {
				let entries = frm.doc.journal_entry.split(", ");
				if (entries.length === 1) {
					frappe.set_route("Form", "Journal Entry", entries[0]);
				} else {
					frappe.set_route("List", "Journal Entry", {
						name: ["in", entries]
					});
				}
			});
		}
	},

	posting_date(frm) {
		if (frm.doc.posting_date && frm.doc.company) {
			frm.trigger("fetch_payment_entries");
		}
	},

	company(frm) {
		if (frm.doc.posting_date && frm.doc.company) {
			frm.trigger("fetch_payment_entries");
		}
	},

	fetch_payment_entries(frm) {
		if (!frm.doc.posting_date || !frm.doc.company) {
			frappe.msgprint(__("Please select Posting Date and Company first"));
			return;
		}

		frappe.call({
			method: "akfa_accounting.akfa_accounting.doctype.cash_distribution_entry.cash_distribution_entry.get_payment_entries",
			args: {
				posting_date: frm.doc.posting_date,
				company: frm.doc.company
			},
			freeze: true,
			freeze_message: __("Fetching Payment Entries..."),
			callback: function(r) {
				if (r.message) {
					// Clear existing items
					frm.clear_table("items");

					// Add payment entries grouped by tranzaksiya_turi and currency
					if (r.message.payment_entries && r.message.payment_entries.length > 0) {
						r.message.payment_entries.forEach(function(pe) {
							let row = frm.add_child("items");
							row.tranzaksiya_turi = pe.tranzaksiya_turi || "No Type";
							row.currency = pe.currency;
							row.total_amount = pe.total_amount;
							row.source_account = pe.source_account;
						});

						frm.refresh_field("items");
						frm.trigger("calculate_totals");
						frappe.show_alert({
							message: __("{0} groups fetched", [r.message.payment_entries.length]),
							indicator: "green"
						});
					} else {
						frappe.show_alert({
							message: __("No undistributed Payment Entries found for the selected date"),
							indicator: "orange"
						});
					}
				}
			}
		});
	},

	calculate_totals(frm) {
		let total_received_usd = 0;
		let total_distributed_usd = 0;
		let total_received_uzs = 0;
		let total_distributed_uzs = 0;

		(frm.doc.items || []).forEach(function(item) {
			if (item.currency === "USD") {
				total_received_usd += flt(item.total_amount);
			} else if (item.currency === "UZS") {
				total_received_uzs += flt(item.total_amount);
			}
		});

		(frm.doc.distribution_details || []).forEach(function(item) {
			if (item.currency === "USD") {
				total_distributed_usd += flt(item.amount);
			} else if (item.currency === "UZS") {
				total_distributed_uzs += flt(item.amount);
			}
		});

		frm.set_value("total_received_usd", total_received_usd);
		frm.set_value("total_distributed_usd", total_distributed_usd);
		frm.set_value("difference_usd", total_received_usd - total_distributed_usd);
		
		frm.set_value("total_received_uzs", total_received_uzs);
		frm.set_value("total_distributed_uzs", total_distributed_uzs);
		frm.set_value("difference_uzs", total_received_uzs - total_distributed_uzs);
	}
});

frappe.ui.form.on("Cash Distribution Detail", {
	currency(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn);
		if (row.currency && frm.doc.company) {
			// Set creditors account based on currency
			let account_number = row.currency === "USD" ? "2110" : "2111";
			frappe.call({
				method: "frappe.client.get_value",
				args: {
					doctype: "Account",
					filters: {
						account_number: account_number,
						company: frm.doc.company
					},
					fieldname: "name"
				},
				callback: function(r) {
					if (r.message) {
						frappe.model.set_value(cdt, cdn, "creditors_account", r.message.name);
					}
				}
			});
		}
		frm.trigger("calculate_totals");
	},

	amount(frm, cdt, cdn) {
		frm.trigger("calculate_totals");
	},

	distribution_details_add(frm, cdt, cdn) {
		// Default to USD
		frappe.model.set_value(cdt, cdn, "currency", "USD");
	},

	distribution_details_remove(frm) {
		frm.trigger("calculate_totals");
	}
});
