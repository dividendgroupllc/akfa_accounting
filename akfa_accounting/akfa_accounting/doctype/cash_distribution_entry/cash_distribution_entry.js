// Copyright (c) 2025, Asadbek and contributors
// For license information, please see license.txt

frappe.ui.form.on("Cash Distribution Entry", {
	onload(frm) {
		// Filter Aripov account to only show 1114 and 1115
		frm.set_query("aripov_account", function() {
			return {
				filters: {
					"account_number": ["in", ["1114", "1115"]],
					"company": frm.doc.company
				}
			};
		});
	},

	refresh(frm) {
		// Add custom button to fetch data
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Fetch Data"), function() {
				frm.trigger("fetch_all_data");
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
		if (frm.doc.posting_date && frm.doc.company && frm.doc.aripov_account) {
			frm.trigger("fetch_all_data");
		}
	},

	company(frm) {
		// Clear aripov_account when company changes
		frm.set_value("aripov_account", "");
		frm.set_value("account_balance", 0);
	},

	aripov_account(frm) {
		if (frm.doc.aripov_account && frm.doc.posting_date && frm.doc.company) {
			frm.trigger("fetch_all_data");
		}
	},

	fetch_all_data(frm) {
		if (!frm.doc.posting_date || !frm.doc.company || !frm.doc.aripov_account) {
			frappe.msgprint(__("Please select Posting Date, Company, and Aripov Account first"));
			return;
		}

		frappe.call({
			method: "akfa_accounting.akfa_accounting.doctype.cash_distribution_entry.cash_distribution_entry.get_cash_distribution_data",
			args: {
				aripov_account: frm.doc.aripov_account,
				posting_date: frm.doc.posting_date,
				company: frm.doc.company
			},
			freeze: true,
			freeze_message: __("Fetching Data..."),
			callback: function(r) {
				if (r.message) {
					// Set account balance
					frm.set_value("account_balance", r.message.account_balance || 0);

					// Clear existing items
					frm.clear_table("items");
					frm.clear_table("transfer_items");
					frm.clear_table("rasxod_items");

					// 1. Populate Davron Tushumlari (Reference)
					if (r.message.davron_items && r.message.davron_items.length > 0) {
						r.message.davron_items.forEach(function(item) {
							let row = frm.add_child("items");
							row.tranzaksiya_turi = item.tranzaksiya_turi || "No Type";
							row.currency = item.currency;
							row.total_amount = item.total_amount;
							row.source_account = item.source_account;
						});
					}

					// 2. Populate Internal Transfers
					if (r.message.transfer_items && r.message.transfer_items.length > 0) {
						r.message.transfer_items.forEach(function(item) {
							let row = frm.add_child("transfer_items");
							row.payment_entry = item.payment_entry;
							row.currency = item.currency;
							row.amount = item.amount;
							row.source_account = item.source_account;
						});
					}

					// 3. Populate Hamidulla Kassa Rasxod
					if (r.message.rasxod_items && r.message.rasxod_items.length > 0) {
						r.message.rasxod_items.forEach(function(item) {
							let row = frm.add_child("rasxod_items");
							row.posting_date = item.posting_date;
							row.kassa_rasxod = item.kassa_rasxod;
							row.amount_usd = item.amount_usd;
							row.amount_uzs = item.amount_uzs;
						});
					}

					frm.refresh_field("items");
					frm.refresh_field("transfer_items");
					frm.refresh_field("rasxod_items");
					frm.trigger("calculate_totals");

					// Show summary
					let transfer_count = (r.message.transfer_items || []).length;
					let rasxod_count = (r.message.rasxod_items || []).length;
					frappe.show_alert({
						message: __("Data fetched: {0} transfers, {1} rasxod entries", [transfer_count, rasxod_count]),
						indicator: "green"
					});
				}
			}
		});
	},

	// Legacy function for backward compatibility
	fetch_payment_entries(frm) {
		frm.trigger("fetch_all_data");
	},

	calculate_totals(frm) {
		// Davron Tushumlari (Reference only)
		let davron_received_usd = 0;
		let davron_received_uzs = 0;
		(frm.doc.items || []).forEach(function(item) {
			if (item.currency === "USD") {
				davron_received_usd += flt(item.total_amount);
			} else if (item.currency === "UZS") {
				davron_received_uzs += flt(item.total_amount);
			}
		});
		frm.set_value("davron_received_usd", davron_received_usd);
		frm.set_value("davron_received_uzs", davron_received_uzs);

		// Internal Transfers TO ARIPOV
		let internal_transfers_usd = 0;
		let internal_transfers_uzs = 0;
		(frm.doc.transfer_items || []).forEach(function(item) {
			if (item.currency === "USD") {
				internal_transfers_usd += flt(item.amount);
			} else if (item.currency === "UZS") {
				internal_transfers_uzs += flt(item.amount);
			}
		});
		frm.set_value("internal_transfers_usd", internal_transfers_usd);
		frm.set_value("internal_transfers_uzs", internal_transfers_uzs);

		// Hamidulla Kassa Rasxod (investor qopladi)
		let hamidulla_rasxod_usd = 0;
		let hamidulla_rasxod_uzs = 0;
		(frm.doc.rasxod_items || []).forEach(function(item) {
			hamidulla_rasxod_usd += flt(item.amount_usd);
			hamidulla_rasxod_uzs += flt(item.amount_uzs);
		});
		frm.set_value("hamidulla_rasxod_usd", hamidulla_rasxod_usd);
		frm.set_value("hamidulla_rasxod_uzs", hamidulla_rasxod_uzs);

		// ARIPOV TOTAL = Internal Transfers + Hamidulla Rasxod
		let aripov_total_usd = internal_transfers_usd + hamidulla_rasxod_usd;
		let aripov_total_uzs = internal_transfers_uzs + hamidulla_rasxod_uzs;
		frm.set_value("aripov_total_usd", aripov_total_usd);
		frm.set_value("aripov_total_uzs", aripov_total_uzs);

		// Total Distributed (from distribution_details)
		let total_distributed_usd = 0;
		let total_distributed_uzs = 0;
		(frm.doc.distribution_details || []).forEach(function(item) {
			if (item.currency === "USD") {
				total_distributed_usd += flt(item.amount);
			} else if (item.currency === "UZS") {
				total_distributed_uzs += flt(item.amount);
			}
		});
		frm.set_value("total_distributed_usd", total_distributed_usd);
		frm.set_value("total_distributed_uzs", total_distributed_uzs);

		// Difference = Aripov Total - Distributed (must be >= 0)
		frm.set_value("difference_usd", aripov_total_usd - total_distributed_usd);
		frm.set_value("difference_uzs", aripov_total_uzs - total_distributed_uzs);

		// Keep legacy fields for backward compatibility
		frm.set_value("total_received_usd", aripov_total_usd);
		frm.set_value("total_received_uzs", aripov_total_uzs);
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
