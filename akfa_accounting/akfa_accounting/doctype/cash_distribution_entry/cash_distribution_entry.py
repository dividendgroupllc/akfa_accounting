# Copyright (c) 2025, Asadbek and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

# Account number constants
ARIPOV_ACCOUNTS = ['1114', '1115']
DAVRON_ACCOUNTS = ['1110', '1111']
HAMIDULLA_MODES = {
	'USD': 'Наличный USD H',
	'UZS': 'Наличный UZS H'
}


def get_exchange_rate_with_fallback(posting_date):
	"""Get exchange rate for the posting date with fallback to latest available rate"""
	exchange_rate = frappe.db.get_value(
		"Currency Exchange",
		{"from_currency": "USD", "to_currency": "UZS", "date": posting_date},
		"exchange_rate"
	)
	
	if not exchange_rate:
		latest_rate = frappe.db.sql("""
			SELECT exchange_rate
			FROM `tabCurrency Exchange`
			WHERE from_currency = 'USD'
				AND to_currency = 'UZS'
				AND date <= %s
			ORDER BY date DESC
			LIMIT 1
		""", (posting_date,), as_dict=True)
		
		if latest_rate:
			exchange_rate = latest_rate[0].exchange_rate
	
	return flt(exchange_rate) or 1


class CashDistributionEntry(Document):
	def validate(self):
		self.validate_exchange_rate()
		self.set_party_currency()
		self.set_distribution_accounts()
		self.calculate_totals()
		self.validate_difference()

	def validate_exchange_rate(self):
		"""Check if exchange rate exists for the posting date.
		If not found for exact date, use the most recent available rate.
		"""
		exchange_rate = frappe.db.get_value(
			"Currency Exchange",
			{"from_currency": "USD", "to_currency": "UZS", "date": self.posting_date},
			"exchange_rate"
		)

		# If not found, get the most recent rate before or on posting date
		if not exchange_rate:
			latest_rate = frappe.db.sql("""
				SELECT exchange_rate, date
				FROM `tabCurrency Exchange`
				WHERE from_currency = 'USD'
					AND to_currency = 'UZS'
					AND date <= %s
				ORDER BY date DESC
				LIMIT 1
			""", (self.posting_date,), as_dict=True)
			
			if latest_rate:
				exchange_rate = latest_rate[0].exchange_rate
				frappe.msgprint(
					_("Using exchange rate from {0} (rate: {1})").format(
						frappe.utils.formatdate(latest_rate[0].date),
						exchange_rate
					),
					alert=True
				)

		if not exchange_rate:
			frappe.throw(
				_("No Currency Exchange rate found for USD to UZS. Please add an exchange rate first.")
			)

	def set_party_currency(self):
		"""Set party_currency from Party Financial Defaults"""
		for row in self.distribution_details:
			if row.supplier and self.company and not row.party_currency:
				party_currency = frappe.db.get_value(
					"Party Financial Defaults",
					{"party_type": "Supplier", "party": row.supplier, "company": self.company},
					"currency"
				)
				if party_currency:
					row.party_currency = party_currency

	def set_distribution_accounts(self):
		"""Set creditors account based on party_currency (supplier's main currency)"""
		for row in self.distribution_details:
			if row.party_currency and self.company:
				account_number = "2110" if row.party_currency == "USD" else "2111"
				creditors_account = frappe.db.get_value(
					"Account",
					{"account_number": account_number, "company": self.company},
					"name"
				)
				if creditors_account:
					row.creditors_account = creditors_account

	def calculate_totals(self):
		"""Calculate totals based on new business logic:
		ARIPOV TOTAL = Internal Transfers + Hamidulla Rasxod
		"""
		# Davron Tushumlari (Reference only)
		self.davron_received_usd = sum(
			flt(item.total_amount) for item in self.items
			if item.currency == "USD"
		)
		self.davron_received_uzs = sum(
			flt(item.total_amount) for item in self.items
			if item.currency == "UZS"
		)

		# Internal Transfers TO ARIPOV
		self.internal_transfers_usd = sum(
			flt(t.amount) for t in self.transfer_items
			if t.currency == "USD"
		)
		self.internal_transfers_uzs = sum(
			flt(t.amount) for t in self.transfer_items
			if t.currency == "UZS"
		)

		# Hamidulla Kassa Rasxod (investor qopladi, converted to USD)
		self.hamidulla_rasxod_usd = sum(flt(r.amount_usd) for r in self.rasxod_items)

		# ARIPOV TOTAL = Internal Transfers + Hamidulla Rasxod
		self.aripov_total_usd = flt(self.internal_transfers_usd) + flt(self.hamidulla_rasxod_usd)
		self.aripov_total_uzs = flt(self.internal_transfers_uzs)

		# Total Distributed (from distribution_details)
		self.total_distributed_usd = sum(
			flt(item.amount) for item in self.distribution_details
			if item.currency == "USD"
		)
		self.total_distributed_uzs = sum(
			flt(item.amount) for item in self.distribution_details
			if item.currency == "UZS"
		)

		# Difference = Aripov Total - Distributed (must be >= 0)
		self.difference_usd = flt(self.aripov_total_usd) - flt(self.total_distributed_usd)
		self.difference_uzs = flt(self.aripov_total_uzs) - flt(self.total_distributed_uzs)

		# Keep legacy fields for backward compatibility
		self.total_received_usd = self.aripov_total_usd
		self.total_received_uzs = self.aripov_total_uzs

	def validate_difference(self):
		"""Ensure total distributed doesn't exceed Aripov total"""
		if self.docstatus == 1:
			if flt(self.difference_usd) < 0:
				frappe.throw(
					_("USD: Total Distributed ({0}) cannot exceed Aripov Total ({1}). Difference: {2}").format(
						self.total_distributed_usd, self.aripov_total_usd, self.difference_usd
					)
				)
			if flt(self.difference_uzs) < 0:
				frappe.throw(
					_("UZS: Total Distributed ({0}) cannot exceed Aripov Total ({1}). Difference: {2}").format(
						self.total_distributed_uzs, self.aripov_total_uzs, self.difference_uzs
					)
				)

	def on_submit(self):
		"""Create Journal Entry and mark Kassa Rasxod as distributed"""
		self.create_distribution_journal_entry()
		self.mark_kassa_rasxod_as_distributed()
		self.mark_payment_entries_as_distributed()

	def on_cancel(self):
		"""Cancel linked Journal Entry and unmark distributed items"""
		self.cancel_distribution_journal_entry()
		self.unmark_kassa_rasxod()
		self.unmark_payment_entries()

	def create_distribution_journal_entry(self):
		"""Create a single Journal Entry for all distributions.
		
		Logic:
		- Credit Aripov accounts (1114 USD, 1115 UZS) - money going out
		- Debit Creditors accounts (2110 USD, 2111 UZS) - supplier debt recorded
		- Creditors account selected based on supplier's currency (party_currency)
		"""
		if not self.distribution_details:
			return
		
		# Get exchange rate (with fallback to latest)
		exchange_rate = get_exchange_rate_with_fallback(self.posting_date)
		
		company_currency = frappe.db.get_value("Company", self.company, "default_currency")
		
		# Get Aripov accounts
		aripov_usd_account = frappe.db.get_value(
			"Account", {"account_number": "1114", "company": self.company}, "name"
		)
		aripov_uzs_account = frappe.db.get_value(
			"Account", {"account_number": "1115", "company": self.company}, "name"
		)
		
		# Calculate totals by payment currency
		total_usd_distributed = sum(
			flt(item.amount) for item in self.distribution_details if item.currency == "USD"
		)
		total_uzs_distributed = sum(
			flt(item.amount) for item in self.distribution_details if item.currency == "UZS"
		)
		
		if total_usd_distributed == 0 and total_uzs_distributed == 0:
			return
		
		# Create Journal Entry
		je = frappe.new_doc("Journal Entry")
		je.voucher_type = "Journal Entry"
		je.posting_date = self.posting_date
		je.company = self.company
		je.multi_currency = 1
		je.user_remark = _("Cash Distribution Entry: {0}").format(self.name)
		
		# Calculate exchange rates for JE
		usd_exchange_rate = flt(exchange_rate) if company_currency == "UZS" else 1
		uzs_exchange_rate = 1 if company_currency == "UZS" else (1 / flt(exchange_rate) if exchange_rate else 1)
		
		# Row 1: Credit Aripov USD account (money going out)
		if total_usd_distributed > 0 and aripov_usd_account:
			je.append("accounts", {
				"account": aripov_usd_account,
				"account_currency": "USD",
				"exchange_rate": usd_exchange_rate,
				"debit_in_account_currency": 0,
				"credit_in_account_currency": total_usd_distributed,
			})
		
		# Row 2: Credit Aripov UZS account (money going out)
		if total_uzs_distributed > 0 and aripov_uzs_account:
			je.append("accounts", {
				"account": aripov_uzs_account,
				"account_currency": "UZS",
				"exchange_rate": uzs_exchange_rate,
				"debit_in_account_currency": 0,
				"credit_in_account_currency": total_uzs_distributed,
			})
		
		# Group distributions by supplier and party_currency
		# Key: (supplier, party_currency, payment_currency)
		supplier_groups = {}
		for item in self.distribution_details:
			if flt(item.amount) <= 0:
				continue
			key = (item.supplier, item.party_currency or item.currency, item.currency)
			if key not in supplier_groups:
				supplier_groups[key] = 0
			supplier_groups[key] += flt(item.amount)
		
		# Rows 3+: Debit Creditors accounts for each supplier
		for (supplier, party_currency, payment_currency), amount in supplier_groups.items():
			# Determine creditors account based on supplier's currency
			creditors_account_number = "2110" if party_currency == "USD" else "2111"
			creditors_account = frappe.db.get_value(
				"Account", {"account_number": creditors_account_number, "company": self.company}, "name"
			)
			
			if not creditors_account:
				frappe.throw(_("Creditors Account ({0}) not found").format(creditors_account_number))
			
			# Convert amount if payment currency differs from supplier currency
			if payment_currency != party_currency:
				if payment_currency == "UZS" and party_currency == "USD":
					# Pay in UZS, supplier is USD → convert UZS to USD
					amount_in_party_currency = flt(amount) / flt(exchange_rate)
				elif payment_currency == "USD" and party_currency == "UZS":
					# Pay in USD, supplier is UZS → convert USD to UZS
					amount_in_party_currency = flt(amount) * flt(exchange_rate)
				else:
					amount_in_party_currency = amount
			else:
				amount_in_party_currency = amount
			
			# Calculate exchange rate for this entry
			if party_currency == company_currency:
				party_exchange_rate = 1
			elif party_currency == "USD" and company_currency == "UZS":
				party_exchange_rate = flt(exchange_rate)
			elif party_currency == "UZS" and company_currency == "USD":
				party_exchange_rate = 1 / flt(exchange_rate) if exchange_rate else 1
			else:
				party_exchange_rate = 1
			
			je.append("accounts", {
				"account": creditors_account,
				"party_type": "Supplier",
				"party": supplier,
				"account_currency": party_currency,
				"exchange_rate": party_exchange_rate,
				"debit_in_account_currency": amount_in_party_currency,
				"credit_in_account_currency": 0,
			})
		
		je.insert()
		je.submit()
		
		# Save JE reference
		frappe.db.set_value("Cash Distribution Entry", self.name, "journal_entry", je.name)
		frappe.msgprint(_("Journal Entry created: {0}").format(je.name))

	def cancel_distribution_journal_entry(self):
		"""Cancel linked Journal Entry"""
		je_names = frappe.db.get_value("Cash Distribution Entry", self.name, "journal_entry")
		if je_names:
			for je_name in je_names.split(", "):
				je_name = je_name.strip()
				if frappe.db.exists("Journal Entry", je_name):
					je = frappe.get_doc("Journal Entry", je_name)
					if je.docstatus == 1:
						je.cancel()
			frappe.msgprint(_("Journal Entries cancelled"))

	def mark_kassa_rasxod_as_distributed(self):
		"""Mark Hamidulla Rasxod entries as distributed"""
		for item in self.rasxod_items:
			if item.kassa_rasxod:
				frappe.db.set_value("Kassa Rasxod", item.kassa_rasxod, "custom_is_distributed", 1)

	def unmark_kassa_rasxod(self):
		"""Unmark Kassa Rasxod when cancelled"""
		for item in self.rasxod_items:
			if item.kassa_rasxod:
				frappe.db.set_value("Kassa Rasxod", item.kassa_rasxod, "custom_is_distributed", 0)

	def mark_payment_entries_as_distributed(self):
		"""Mark Internal Transfer Payment Entries as distributed"""
		for item in self.transfer_items:
			if item.payment_entry:
				frappe.db.set_value("Payment Entry", item.payment_entry, "custom_is_distributed", 1)

	def unmark_payment_entries(self):
		"""Unmark Payment Entries when this document is cancelled"""
		for item in self.transfer_items:
			if item.payment_entry:
				frappe.db.set_value("Payment Entry", item.payment_entry, "custom_is_distributed", 0)


def get_account_by_number(account_number, company):
	"""Get account name by account number and company"""
	return frappe.db.get_value(
		"Account",
		{"account_number": account_number, "company": company},
		"name"
	)


def get_accounts_by_numbers(account_numbers, company):
	"""Get list of account names by account numbers"""
	accounts = []
	for num in account_numbers:
		account = get_account_by_number(num, company)
		if account:
			accounts.append(account)
	return accounts


@frappe.whitelist()
def get_cash_distribution_data(posting_date, company):
	"""Fetch all data for Cash Distribution Entry

	Now fetches both USD and UZS account balances,
	and converts Hamidulla UZS expenses to USD.
	"""

	# Get exchange rate for UZS → USD conversion (with fallback to latest)
	exchange_rate = get_exchange_rate_with_fallback(posting_date)

	# 1. Get Davron Tushumlari (Reference)
	davron_accounts = get_accounts_by_numbers(DAVRON_ACCOUNTS, company)

	davron_items = frappe.db.sql("""
		SELECT
			IFNULL(pe.custom_tranzaksiya_turi, 'No Type') as tranzaksiya_turi,
			pe.paid_to_account_currency as currency,
			CASE
				WHEN pe.paid_to_account_currency = 'UZS' THEN SUM(pe.received_amount)
				ELSE SUM(pe.paid_amount)
			END as total_amount,
			COUNT(*) as pe_count
		FROM `tabPayment Entry` pe
		WHERE pe.posting_date = %s
			AND pe.payment_type = 'Receive'
			AND pe.paid_to IN %s
			AND pe.company = %s
			AND pe.docstatus = 1
		GROUP BY pe.custom_tranzaksiya_turi, pe.paid_to_account_currency
		ORDER BY pe.paid_to_account_currency, pe.custom_tranzaksiya_turi
	""", (posting_date, davron_accounts, company), as_dict=True)

	# Add source account for display
	for item in davron_items:
		item['source_account'] = get_account_by_number("1114" if item['currency'] == "USD" else "1115", company)

	# 2. Get Internal Transfers (Davron → Aripov) for BOTH accounts
	aripov_usd_account = get_account_by_number("1114", company)
	aripov_uzs_account = get_account_by_number("1115", company)
	aripov_accounts = [acc for acc in [aripov_usd_account, aripov_uzs_account] if acc]

	transfer_items = []
	if aripov_accounts:
		transfer_items = frappe.db.sql("""
			SELECT
				pe.name as payment_entry,
				pe.paid_to_account_currency as currency,
				pe.paid_amount as amount,
				pe.paid_from as source_account
			FROM `tabPayment Entry` pe
			WHERE pe.posting_date = %s
				AND pe.payment_type = 'Internal Transfer'
				AND pe.paid_to IN %s
				AND pe.company = %s
				AND pe.docstatus = 1
				AND IFNULL(pe.custom_is_distributed, 0) = 0
			ORDER BY pe.name
		""", (posting_date, aripov_accounts, company), as_dict=True)

	# 3. Get Hamidulla Kassa Rasxod (BOTH USD and UZS, convert UZS to USD)
	rasxod_items = []

	# Get USD Rasxod
	usd_rasxod = frappe.db.sql("""
		SELECT
			kr.name as kassa_rasxod,
			kr.posting_date,
			kr.total_amount as amount_usd,
			'USD' as original_currency
		FROM `tabKassa Rasxod` kr
		WHERE kr.posting_date = %s
			AND kr.mode_of_payment = %s
			AND kr.docstatus = 1
			AND IFNULL(kr.custom_is_distributed, 0) = 0
		ORDER BY kr.posting_date
	""", (posting_date, HAMIDULLA_MODES['USD']), as_dict=True)

	# Get UZS Rasxod - total_amount is already in USD (converted in Kassa Rasxod)
	uzs_rasxod = frappe.db.sql("""
		SELECT
			kr.name as kassa_rasxod,
			kr.posting_date,
			kr.total_amount as amount_usd,
			'UZS' as original_currency
		FROM `tabKassa Rasxod` kr
		WHERE kr.posting_date = %s
			AND kr.mode_of_payment = %s
			AND kr.docstatus = 1
			AND IFNULL(kr.custom_is_distributed, 0) = 0
		ORDER BY kr.posting_date
	""", (posting_date, HAMIDULLA_MODES['UZS']), as_dict=True)

	# total_amount is already converted to USD in Kassa Rasxod doctype
	# No additional conversion needed

	rasxod_items = usd_rasxod + uzs_rasxod

	# 4. Get BOTH account balances
	from erpnext.accounts.utils import get_balance_on
	aripov_usd_balance = get_balance_on(account=aripov_usd_account, date=posting_date) if aripov_usd_account else 0
	aripov_uzs_balance = get_balance_on(account=aripov_uzs_account, date=posting_date) if aripov_uzs_account else 0

	return {
		"davron_items": davron_items,
		"transfer_items": transfer_items,
		"rasxod_items": rasxod_items,
		"aripov_usd_balance": aripov_usd_balance or 0,
		"aripov_uzs_balance": aripov_uzs_balance or 0,
		"exchange_rate": exchange_rate
	}


# Keep the old function for backward compatibility
@frappe.whitelist()
def get_payment_entries(posting_date, company):
	"""Legacy function - kept for backward compatibility"""

	usd_davron_account = get_account_by_number("1110", company)
	uzs_davron_account = get_account_by_number("1111", company)
	usd_aripov_account = get_account_by_number("1114", company)
	uzs_aripov_account = get_account_by_number("1115", company)

	davron_accounts = []
	if usd_davron_account:
		davron_accounts.append(usd_davron_account)
	if uzs_davron_account:
		davron_accounts.append(uzs_davron_account)

	if not davron_accounts:
		frappe.throw(_("No Davron kassa accounts (1110, 1111) found in Company {0}").format(company))

	payment_entries = frappe.db.sql("""
		SELECT
			IFNULL(pe.custom_tranzaksiya_turi, 'No Type') as tranzaksiya_turi,
			pe.paid_to_account_currency as currency,
			CASE
				WHEN pe.paid_to_account_currency = 'USD' THEN %s
				ELSE %s
			END as source_account,
			CASE
				WHEN pe.paid_to_account_currency = 'UZS' THEN SUM(pe.received_amount)
				ELSE SUM(pe.paid_amount)
			END as total_amount,
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
