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
	supplier(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn);
		if (row.supplier && frm.doc.company) {
			// Fetch party_currency from Party Financial Defaults
			frappe.call({
				method: "frappe.client.get_value",
				args: {
					doctype: "Party Financial Defaults",
					filters: {
						party_type: "Supplier",
						party: row.supplier,
						company: frm.doc.company
					},
					fieldname: "currency"
				},
				callback: function(r) {
					if (r.message && r.message.currency) {
						frappe.model.set_value(cdt, cdn, "party_currency", r.message.currency);
						
						// Set creditors account based on party_currency
						let account_number = r.message.currency === "USD" ? "2110" : "2111";
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
							callback: function(acc_r) {
								if (acc_r.message) {
									frappe.model.set_value(cdt, cdn, "creditors_account", acc_r.message.name);
								}
							}
						});
					}
				}
			});
		}
	},

	currency(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn);
		
		// If currency changed and amount exists, recalculate USD equivalent
		if (flt(row.amount) > 0) {
			if (row.currency === "UZS") {
				convert_uzs_to_usd(frm, cdt, cdn, row.amount);
			} else if (row.currency === "USD") {
				// USD to USD - same value
				frappe.model.set_value(cdt, cdn, "usd_ekvivalent", row.amount);
			}
		}
		
		frm.trigger("calculate_totals");
	},

	amount(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn);
		let amount = flt(row.amount);
		
		if (amount <= 0) {
			frappe.model.set_value(cdt, cdn, "usd_ekvivalent", 0);
			frm.trigger("calculate_totals");
			return;
		}
		
		if (row.currency === "UZS") {
			// UZS amount entered, convert to USD
			convert_uzs_to_usd(frm, cdt, cdn, amount);
		} else if (row.currency === "USD") {
			// USD to USD - same value
			frappe.model.set_value(cdt, cdn, "usd_ekvivalent", amount);
		}
		
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

function convert_uzs_to_usd(frm, cdt, cdn, uzs_amount) {
	// Convert UZS to USD
	frappe.call({
		method: "akfa_accounting.akfa_accounting.api.payment_entry_api.get_daily_exchange_rates",
		args: {
			date: frm.doc.posting_date
		},
		callback: function(r) {
			if (r.message && r.message.usd_to_uzs) {
				let exchange_rate = flt(r.message.usd_to_uzs);
				if (exchange_rate > 0) {
					let usd_amount = flt(uzs_amount / exchange_rate, 2);
					
					// Set USD equivalent
					frappe.model.set_value(cdt, cdn, "usd_ekvivalent", usd_amount);
					
					frappe.show_alert({
						message: __("{0} UZS → {1} USD (Kurs: {2})", [
							format_number(uzs_amount),
							format_number(usd_amount, null, 2),
							format_number(exchange_rate)
						]),
						indicator: "green"
					}, 5);
					
					frm.trigger("calculate_totals");
				}
			} else {
				frappe.msgprint({
					title: __("Kurs topilmadi"),
					message: __("{0} sanasi uchun valyuta kursi mavjud emas.", [frm.doc.posting_date]),
					indicator: "red"
				});
			}
		}
	});
}
