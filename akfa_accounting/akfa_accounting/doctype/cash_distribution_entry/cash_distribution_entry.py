# Copyright (c) 2025, Asadbek and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class CashDistributionEntry(Document):
	def validate(self):
		self.set_distribution_accounts()
		self.calculate_totals()
		self.validate_difference()

	def set_distribution_accounts(self):
		"""Set creditors account for each distribution detail row based on currency"""
		for row in self.distribution_details:
			if row.currency and self.company:
				if row.currency == "USD":
					creditors_account_number = "2110"
				else:  # UZS
					creditors_account_number = "2111"
				
				creditors_account = frappe.db.get_value(
					"Account",
					{"account_number": creditors_account_number, "company": self.company},
					"name"
				)
				if creditors_account:
					row.creditors_account = creditors_account

	def calculate_totals(self):
		"""Calculate total received and distributed amounts by currency"""
		# USD totals
		self.total_received_usd = sum(
			flt(item.total_amount) for item in self.items 
			if item.currency == "USD"
		)
		self.total_distributed_usd = sum(
			flt(item.amount) for item in self.distribution_details 
			if item.currency == "USD"
		)
		self.difference_usd = flt(self.total_received_usd) - flt(self.total_distributed_usd)
		
		# UZS totals
		self.total_received_uzs = sum(
			flt(item.total_amount) for item in self.items 
			if item.currency == "UZS"
		)
		self.total_distributed_uzs = sum(
			flt(item.amount) for item in self.distribution_details 
			if item.currency == "UZS"
		)
		self.difference_uzs = flt(self.total_received_uzs) - flt(self.total_distributed_uzs)

	def validate_difference(self):
		"""Ensure total received equals total distributed before submit"""
		if self.docstatus == 1:
			if flt(self.difference_usd) != 0:
				frappe.throw(
					_("USD: Total Received ({0}) must equal Total Distributed ({1}). Difference: {2}").format(
						self.total_received_usd, self.total_distributed_usd, self.difference_usd
					)
				)
			if flt(self.difference_uzs) != 0:
				frappe.throw(
					_("UZS: Total Received ({0}) must equal Total Distributed ({1}). Difference: {2}").format(
						self.total_received_uzs, self.total_distributed_uzs, self.difference_uzs
					)
				)

	def on_submit(self):
		"""Create Journal Entries and mark Payment Entries as distributed"""
		self.create_journal_entries()
		self.mark_payment_entries_as_distributed()

	def on_cancel(self):
		"""Cancel linked Journal Entries and unmark Payment Entries"""
		self.cancel_journal_entries()
		self.unmark_payment_entries()

	def create_journal_entries(self):
		"""Create separate Journal Entries for USD and UZS distributions
		
		Journal Entry Structure:
		1. 2110 (Creditors) Credit - Investor (Ofis GL) gives money
		2. 1114 (Aripov Kassa) Debit - Money enters Aripov cashbox
		3. 2110 (Creditors) Debit - Each supplier gets debt (multiple rows)
		4. 1114 (Aripov Kassa) Credit - Money leaves Aripov cashbox
		"""
		journal_entries = []
		
		for currency in ["USD", "UZS"]:
			# Get distribution items for this currency
			currency_items = [item for item in self.distribution_details if item.currency == currency]
			if not currency_items:
				continue
			
			# Get investor for this currency
			investor = self.investor_usd if currency == "USD" else self.investor_uzs
			if not investor:
				frappe.throw(_("Please select Investor (Ofis GL) for {0}").format(currency))
			
			# Get Aripov kassa account (1114 for USD, 1115 for UZS)
			aripov_account_number = "1114" if currency == "USD" else "1115"
			aripov_account = frappe.db.get_value(
				"Account",
				{"account_number": aripov_account_number, "company": self.company},
				"name"
			)
			
			# Get creditors account (2110 for USD, 2111 for UZS)
			creditors_account_number = "2110" if currency == "USD" else "2111"
			creditors_account = frappe.db.get_value(
				"Account",
				{"account_number": creditors_account_number, "company": self.company},
				"name"
			)
			
			if not aripov_account:
				frappe.throw(_("Aripov Kassa Account ({0}) not found for {1}").format(aripov_account_number, currency))
			if not creditors_account:
				frappe.throw(_("Creditors Account ({0}) not found for {1}").format(creditors_account_number, currency))
			
			# Group by supplier and sum amounts
			supplier_totals = {}
			total_amount = 0
			for item in currency_items:
				if item.supplier not in supplier_totals:
					supplier_totals[item.supplier] = 0
				supplier_totals[item.supplier] += flt(item.amount)
				total_amount += flt(item.amount)
			
			je = frappe.new_doc("Journal Entry")
			je.voucher_type = "Journal Entry"
			je.posting_date = self.posting_date
			je.company = self.company
			je.multi_currency = 1
			je.user_remark = _("Cash Distribution Entry: {0} ({1})").format(self.name, currency)

			# Row 1: Investor (Ofis GL) gives money - 2110 Credit
			je.append("accounts", {
				"account": creditors_account,
				"party_type": "Supplier",
				"party": investor,
				"debit_in_account_currency": 0,
				"credit_in_account_currency": total_amount,
			})
			
			# Row 2: Money enters Aripov Kassa - 1114 Debit
			je.append("accounts", {
				"account": aripov_account,
				"debit_in_account_currency": total_amount,
				"credit_in_account_currency": 0,
			})

			# Row 3+: Each supplier gets debt - 2110 Debit
			for supplier, amount in supplier_totals.items():
				je.append("accounts", {
					"account": creditors_account,
					"party_type": "Supplier",
					"party": supplier,
					"debit_in_account_currency": amount,
					"credit_in_account_currency": 0,
				})

			# Last Row: Money leaves Aripov Kassa - 1114 Credit
			je.append("accounts", {
				"account": aripov_account,
				"debit_in_account_currency": 0,
				"credit_in_account_currency": total_amount,
			})

			je.insert()
			je.submit()
			journal_entries.append(je.name)
		
		if journal_entries:
			# Store all journal entry names
			frappe.db.set_value("Cash Distribution Entry", self.name, "journal_entry", ", ".join(journal_entries))
			frappe.msgprint(_("Journal Entries created: {0}").format(", ".join(journal_entries)))

	def cancel_journal_entries(self):
		"""Cancel all linked Journal Entries"""
		je_names = frappe.db.get_value("Cash Distribution Entry", self.name, "journal_entry")
		if je_names:
			for je_name in je_names.split(", "):
				je_name = je_name.strip()
				if frappe.db.exists("Journal Entry", je_name):
					je = frappe.get_doc("Journal Entry", je_name)
					if je.docstatus == 1:
						je.cancel()
			frappe.msgprint(_("Journal Entries cancelled"))

	def mark_payment_entries_as_distributed(self):
		"""Mark all Payment Entries as distributed based on tranzaksiya_turi"""
		# Get all tranzaksiya_turi from items
		for item in self.items:
			if item.tranzaksiya_turi and item.currency:
				# Get Davron kassa account for this currency (1110 for USD, 1111 for UZS)
				# Payment Entries are received into Davron kassa, then distributed from Aripov kassa
				davron_account_number = "1110" if item.currency == "USD" else "1111"
				davron_account = frappe.db.get_value(
					"Account",
					{"account_number": davron_account_number, "company": self.company},
					"name"
				)
				
				# Mark all PEs with this tranzaksiya_turi on this date as distributed
				frappe.db.sql("""
					UPDATE `tabPayment Entry`
					SET custom_is_distributed = 1
					WHERE posting_date = %s
						AND payment_type = 'Receive'
						AND paid_to = %s
						AND company = %s
						AND docstatus = 1
						AND IFNULL(custom_tranzaksiya_turi, '') = %s
				""", (self.posting_date, davron_account, self.company, item.tranzaksiya_turi or ""))

	def unmark_payment_entries(self):
		"""Unmark Payment Entries when this document is cancelled"""
		for item in self.items:
			if item.tranzaksiya_turi and item.currency:
				davron_account_number = "1110" if item.currency == "USD" else "1111"
				davron_account = frappe.db.get_value(
					"Account",
					{"account_number": davron_account_number, "company": self.company},
					"name"
				)
				
				frappe.db.sql("""
					UPDATE `tabPayment Entry`
					SET custom_is_distributed = 0
					WHERE posting_date = %s
						AND payment_type = 'Receive'
						AND paid_to = %s
						AND company = %s
						AND docstatus = 1
						AND IFNULL(custom_tranzaksiya_turi, '') = %s
				""", (self.posting_date, davron_account, self.company, item.tranzaksiya_turi or ""))


@frappe.whitelist()
def get_payment_entries(posting_date, company):
	"""Fetch undistributed Payment Entries for the given date, grouped by tranzaksiya_turi and currency
	
	Payment Entries go to Davron kassa (1110/1111), but we show Aripov kassa (1114/1115) as source
	because distribution happens from Aripov kassa
	"""
	
	# Get Davron kassa accounts (where Payment Entries are received)
	usd_davron_account = frappe.db.get_value(
		"Account",
		{"account_number": "1110", "company": company},
		"name"
	)
	uzs_davron_account = frappe.db.get_value(
		"Account",
		{"account_number": "1111", "company": company},
		"name"
	)
	
	# Get Aripov kassa accounts (where distribution happens)
	usd_aripov_account = frappe.db.get_value(
		"Account",
		{"account_number": "1114", "company": company},
		"name"
	)
	uzs_aripov_account = frappe.db.get_value(
		"Account",
		{"account_number": "1115", "company": company},
		"name"
	)
	
	davron_accounts = []
	if usd_davron_account:
		davron_accounts.append(usd_davron_account)
	if uzs_davron_account:
		davron_accounts.append(uzs_davron_account)
	
	if not davron_accounts:
		frappe.throw(_("No Davron kassa accounts (1110, 1111) found in Company {0}").format(company))

	# Fetch Payment Entries grouped by tranzaksiya_turi and currency
	payment_entries = frappe.db.sql("""
		SELECT 
			IFNULL(pe.custom_tranzaksiya_turi, 'No Type') as tranzaksiya_turi,
			pe.paid_to_account_currency as currency,
			CASE 
				WHEN pe.paid_to_account_currency = 'USD' THEN %s
				ELSE %s
			END as source_account,
			SUM(pe.paid_amount) as total_amount,
			COUNT(*) as pe_count
		FROM `tabPayment Entry` pe
		WHERE pe.posting_date = %s
			AND pe.payment_type = 'Receive'
			AND pe.paid_to IN %s
			AND pe.company = %s
			AND pe.docstatus = 1
			AND IFNULL(pe.custom_is_distributed, 0) = 0
		GROUP BY pe.custom_tranzaksiya_turi, pe.paid_to_account_currency
		ORDER BY pe.paid_to_account_currency, pe.custom_tranzaksiya_turi
	""", (usd_aripov_account, uzs_aripov_account, posting_date, davron_accounts, company), as_dict=True)

	return {
		"payment_entries": payment_entries
	}
