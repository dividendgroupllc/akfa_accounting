# Copyright (c) 2025, Asadbek and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
import json


class KassaRasxod(Document):
	def validate(self):
		self.validate_currency_exchange_rate()
		self.calculate_item_amounts()
		self.validate_items()

	def on_submit(self):
		"""Create Journal Entries for Rasxod items where date matches posting_date"""
		self.create_journal_entries_for_rasxod()

	def on_cancel(self):
		"""Cancel linked Journal Entries"""
		self.cancel_linked_journal_entries()

	def validate_currency_exchange_rate(self):
		"""Validate that currency exchange rate exists for the posting date"""
		if not self.posting_date:
			return

		exchange_rate = frappe.db.get_value(
			"Currency Exchange",
			{
				"from_currency": "USD",
				"to_currency": "UZS",
				"date": self.posting_date
			},
			"exchange_rate"
		)

		if not exchange_rate:
			frappe.throw(
				_("Currency Exchange rate for USD to UZS on {0} not found.").format(
					frappe.utils.formatdate(self.posting_date)
				),
				title=_("Exchange Rate Missing")
			)

		self.currency_exchange_rate = exchange_rate

	def calculate_item_amounts(self):
		"""Calculate USD/UZS amounts based on mode of payment"""
		if not self.mode_of_payment or not self.currency_exchange_rate or not self.items_data:
			return

		try:
			items = json.loads(self.items_data)
		except:
			return

		for item in items:
			if self.mode_of_payment == "Наличный USD H":
				# USD mode - NO exchange rate calculation
				pass
			else:
				# UZS mode - calculate USD from UZS using exchange rate
				if item.get('paid_amount_uzs'):
					item['paid_amount_usd'] = item['paid_amount_uzs'] / self.currency_exchange_rate

		self.items_data = json.dumps(items)

	def validate_items(self):
		"""Validate items based on rasxod_podochot and mode_of_payment"""
		if not self.items_data:
			return

		try:
			items = json.loads(self.items_data)
		except:
			frappe.throw(_("Invalid items data"))
			return

		for idx, item in enumerate(items, start=1):
			tip = item.get('rasxod_podochot')
			
			if tip == "Расход":
				# Cost Center and Category required
				if not item.get('cost_center'):
					frappe.throw(
						_("Row #{0}: Cost Center is required for Расход").format(idx),
						title=_("Validation Error")
					)
				if not item.get('category'):
					frappe.throw(
						_("Row #{0}: Category (Тип 1) is required for Расход").format(idx),
						title=_("Validation Error")
					)

				# Date required for Rasxod
				if not item.get('date'):
					frappe.throw(
						_("Row #{0}: Date is required for Расход").format(idx),
						title=_("Validation Error")
					)

			elif tip in ["Подотчет приход", "Подотчет расход"]:
				# Employee Group and Employee required
				if not item.get('employee_group'):
					frappe.throw(
						_("Row #{0}: Employee Group (Сектор) is required for {1}").format(idx, tip),
						title=_("Validation Error")
					)
				if not item.get('employee'):
					frappe.throw(
						_("Row #{0}: Employee is required for {1}").format(idx, tip),
						title=_("Validation Error")
					)

			elif tip == "Коплашга":
				# At least one party pair should be filled
				has_party1 = item.get('party_type') and item.get('party')
				has_party2 = item.get('party_type_2') and item.get('party_2')
				
				if not has_party1 and not has_party2:
					frappe.throw(
						_("Row #{0}: At least one Party must be filled for Коплашга").format(idx),
						title=_("Validation Error")
					)

	def create_journal_entries_for_rasxod(self):
		"""Create Journal Entries for Rasxod type items where date == posting_date"""
		if not self.items_data:
			return

		try:
			items = json.loads(self.items_data)
		except:
			return

		# Get cash account from Mode of Payment
		cash_account = frappe.db.get_value(
			"Mode of Payment Account",
			{
				"parent": self.mode_of_payment,
				"parenttype": "Mode of Payment"
			},
			"default_account"
		)

		if not cash_account:
			frappe.throw(_("No default account found for Mode of Payment: {0}").format(self.mode_of_payment))

		# Get company
		company = frappe.db.get_value("Account", cash_account, "company")
		
		# Get default payable account for company
		default_payable_account = frappe.db.get_value("Company", company, "default_payable_account")
		
		# Main cost center for Cash and Payable accounts
		main_cost_center = frappe.db.get_value("Company", company, "cost_center") or "Main - A"

		for idx, item in enumerate(items, start=1):
			tip = item.get('rasxod_podochot')
			item_date = item.get('date')
			
			# Only process Rasxod type where item date equals posting date
			if tip != "Расход" or str(item_date) != str(self.posting_date):
				continue

			# Get expense account from category (category_name is the account name)
			expense_account = item.get('category')
			if not expense_account:
				continue

			# Get amount (USD mode)
			amount = item.get('paid_amount_usd') or 0
			if not amount:
				continue

			# Expense cost center from item (e.g., 5200 - Адм.Расход - A)
			expense_cost_center = item.get('cost_center') or main_cost_center
			party_type = item.get('party_type')
			party = item.get('party')

			# Create Journal Entry
			if party_type and party:
				# Case 2: Party is filled - create 4-line journal entry
				self.create_journal_entry_with_party(
					company=company,
					cash_account=cash_account,
					expense_account=expense_account,
					payable_account=default_payable_account,
					amount=amount,
					expense_cost_center=expense_cost_center,
					main_cost_center=main_cost_center,
					party_type=party_type,
					party=party,
					item_idx=idx,
					izoh=item.get('izoh', '')
				)
			else:
				# Case 1: Party is empty - create 2-line journal entry
				self.create_journal_entry_without_party(
					company=company,
					cash_account=cash_account,
					expense_account=expense_account,
					amount=amount,
					expense_cost_center=expense_cost_center,
					main_cost_center=main_cost_center,
					item_idx=idx,
					izoh=item.get('izoh', '')
				)

	def create_journal_entry_without_party(self, company, cash_account, expense_account, 
										   amount, expense_cost_center, main_cost_center, item_idx, izoh=''):
		"""
		Create Journal Entry when Party is empty (tz-1):
		- Credit: Cash Account (1112) - Cost Center: Main - A
		- Debit: Expense Account (5209) - Cost Center: 5200 (from item)
		"""
		je = frappe.new_doc("Journal Entry")
		je.voucher_type = "Journal Entry"
		je.posting_date = self.posting_date
		je.company = company
		je.user_remark = f"Auto-created from Kassa Rasxod {self.name}, Row #{item_idx}. {izoh}"

		# Row 1: Credit Cash Account - Main cost center
		je.append("accounts", {
			"account": cash_account,
			"credit_in_account_currency": amount,
			"debit_in_account_currency": 0,
			"cost_center": main_cost_center
		})

		# Row 2: Debit Expense Account - Expense cost center from item
		je.append("accounts", {
			"account": expense_account,
			"debit_in_account_currency": amount,
			"credit_in_account_currency": 0,
			"cost_center": expense_cost_center
		})

		je.insert()
		je.submit()

		frappe.msgprint(_("Journal Entry {0} created for Row #{1}").format(
			frappe.utils.get_link_to_form("Journal Entry", je.name), item_idx
		))

	def create_journal_entry_with_party(self, company, cash_account, expense_account, 
										payable_account, amount, expense_cost_center, main_cost_center,
										party_type, party, item_idx, izoh=''):
		"""
		Create Journal Entry when Party is filled (tz-2):
		- Row 1: Credit Payable Account (2110) with Party - Main cost center
		- Row 2: Debit Cash Account (1112) - Main cost center
		- Row 3: Credit Cash Account (1112) - Main cost center
		- Row 4: Debit Expense Account (5209) - Expense cost center
		"""
		je = frappe.new_doc("Journal Entry")
		je.voucher_type = "Journal Entry"
		je.posting_date = self.posting_date
		je.company = company
		je.user_remark = f"Auto-created from Kassa Rasxod {self.name}, Row #{item_idx}. {izoh}"

		# Row 1: Credit Payable Account with Party - Main cost center
		je.append("accounts", {
			"account": payable_account,
			"credit_in_account_currency": amount,
			"debit_in_account_currency": 0,
			"party_type": party_type,
			"party": party,
			"cost_center": main_cost_center
		})

		# Row 2: Debit Cash Account (payment to supplier/party) - Main cost center
		je.append("accounts", {
			"account": cash_account,
			"debit_in_account_currency": amount,
			"credit_in_account_currency": 0,
			"cost_center": main_cost_center
		})

		# Row 3: Credit Cash Account (expense payment) - Main cost center
		je.append("accounts", {
			"account": cash_account,
			"credit_in_account_currency": amount,
			"debit_in_account_currency": 0,
			"cost_center": main_cost_center
		})

		# Row 4: Debit Expense Account - Expense cost center from item
		je.append("accounts", {
			"account": expense_account,
			"debit_in_account_currency": amount,
			"credit_in_account_currency": 0,
			"cost_center": expense_cost_center
		})

		je.insert()
		je.submit()

		frappe.msgprint(_("Journal Entry {0} created for Row #{1} with Party {2}").format(
			frappe.utils.get_link_to_form("Journal Entry", je.name), item_idx, party
		))

	def cancel_linked_journal_entries(self):
		"""Cancel all Journal Entries linked to this Kassa Rasxod"""
		journal_entries = frappe.get_all(
			"Journal Entry",
			filters={
				"user_remark": ["like", f"%Kassa Rasxod {self.name}%"],
				"docstatus": 1
			},
			pluck="name"
		)

		for je_name in journal_entries:
			je = frappe.get_doc("Journal Entry", je_name)
			je.cancel()
			frappe.msgprint(_("Journal Entry {0} cancelled").format(je_name))


@frappe.whitelist()
def get_employees_by_group(employee_group):
	"""Get employees belonging to an Employee Group"""
	if not employee_group:
		return []
	
	employees = frappe.db.sql("""
		SELECT employee, employee_name 
		FROM `tabEmployee Group Table` 
		WHERE parent = %s AND parenttype = 'Employee Group'
	""", employee_group, as_dict=True)
	
	return employees


@frappe.whitelist()
def get_mode_of_payment_balance(mode_of_payment, posting_date=None):
	"""Get account balance for Mode of Payment"""
	if not mode_of_payment:
		return 0
	
	# Get the account linked to Mode of Payment
	account = frappe.db.get_value(
		"Mode of Payment Account",
		{
			"parent": mode_of_payment,
			"parenttype": "Mode of Payment"
		},
		"default_account"
	)
	
	if not account:
		return 0
	
	# Get account balance using ERPNext utility
	from erpnext.accounts.utils import get_balance_on
	
	balance = get_balance_on(
		account=account,
		date=posting_date
	)
	
	return balance or 0
