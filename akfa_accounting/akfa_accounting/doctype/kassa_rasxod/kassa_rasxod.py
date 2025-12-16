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
