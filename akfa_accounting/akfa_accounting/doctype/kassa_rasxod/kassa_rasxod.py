# Copyright (c) 2025, Asadbek and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _


class KassaRasxod(Document):
	def validate(self):
		self.validate_currency_exchange_rate()
		self.get_employee_from_podrazdelenie()
		self.calculate_amounts()

	def get_employee_from_podrazdelenie(self):
		"""Get employee from Employee Podrazdelenie based on date range logic"""
		if not self.posting_date or not self.podrazdelenie:
			return

		result = get_employee_for_date(self.posting_date, self.podrazdelenie)
		if result:
			self.employee = result.get("employee")
			self.employee_name = result.get("employee_name", "")

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

	def calculate_amounts(self):
		"""Calculate USD/UZS amounts based on mode of payment"""
		if not self.mode_of_payment or not self.currency_exchange_rate:
			return

		if self.mode_of_payment in ["Наличные USD", "Наличный USD H"]:
			if self.paid_amount_usd:
				self.paid_amount_uzs = self.paid_amount_usd * self.currency_exchange_rate
		else:
			if self.paid_amount_uzs:
				self.paid_amount_usd = self.paid_amount_uzs / self.currency_exchange_rate


@frappe.whitelist()
def get_employee_for_date(posting_date, podrazdelenie):
	"""
	Get employee based on date range logic:
	- Find the most recent Employee Podrazdelenie record where date <= posting_date
	- For the given podrazdelenie
	"""
	record = frappe.db.sql("""
		SELECT employee, date
		FROM `tabEmployee Podrazdelenie`
		WHERE podrazdelenie = %s
		AND date <= %s
		ORDER BY date DESC
		LIMIT 1
	""", (podrazdelenie, posting_date), as_dict=True)

	if record:
		employee = record[0].employee
		emp_details = frappe.db.get_value(
			"Employee",
			employee,
			["first_name", "last_name"],
			as_dict=True
		)
		employee_name = ""
		if emp_details:
			employee_name = f"{emp_details.get('first_name', '')} {emp_details.get('last_name', '')}".strip()

		return {
			"employee": employee,
			"employee_name": employee_name
		}

	return None


@frappe.whitelist()
def get_mode_of_payment_account(mode_of_payment, company="Akfa"):
	"""
	Get the account linked to Mode of Payment and its balance
	"""
	account = frappe.db.get_value(
		"Mode of Payment Account",
		{
			"parent": mode_of_payment,
			"company": company
		},
		"default_account"
	)

	if not account:
		return None

	# Get account balance using GL Entry
	balance = frappe.db.sql("""
		SELECT SUM(debit) - SUM(credit) as balance
		FROM `tabGL Entry`
		WHERE account = %s
		AND is_cancelled = 0
	""", account, as_dict=True)

	account_balance = balance[0].balance if balance and balance[0].balance else 0

	return {
		"account": account,
		"balance": account_balance
	}
