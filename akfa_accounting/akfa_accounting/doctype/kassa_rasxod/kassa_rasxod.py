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
		"""Get employee from Employee Podrazdelenie"""
		if not self.posting_date or not self.podrazdelenie:
			return
		
		employee = frappe.db.get_value(
			"Employee Podrazdelenie",
			{
				"date": self.posting_date,
				"podrazdelenie": self.podrazdelenie
			},
			"employee"
		)
		
		if employee:
			self.employee = employee
			# Get employee full name
			emp_details = frappe.db.get_value(
				"Employee",
				employee,
				["first_name", "last_name"],
				as_dict=True
			)
			if emp_details:
				full_name = f"{emp_details.get('first_name', '')} {emp_details.get('last_name', '')}".strip()
				self.employee_name = full_name
	
	def validate_currency_exchange_rate(self):
		"""Validate that currency exchange rate exists for the posting date"""
		if not self.posting_date:
			return
		
		# Check if exchange rate exists in Currency Exchange
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
				_("Currency Exchange rate for USD to UZS on {0} not found. Please add the exchange rate in Currency Exchange first.").format(
					frappe.utils.formatdate(self.posting_date)
				),
				title=_("Exchange Rate Missing")
			)
		
		# Set the exchange rate from Currency Exchange
		self.currency_exchange_rate = exchange_rate
	
	def calculate_amounts(self):
		"""Calculate USD/UZS amounts based on mode of payment"""
		if not self.mode_of_payment or not self.currency_exchange_rate:
			return
		
		# Наличные USD - calculate UZS from USD
		if self.mode_of_payment == "Наличные USD":
			if self.paid_amount_usd:
				self.paid_amount_uzs = self.paid_amount_usd * self.currency_exchange_rate
		# Наличные UZS, Перечисления UZS - calculate USD from UZS
		elif self.mode_of_payment in ["Наличные UZS", "Перечисления UZS"]:
			if self.paid_amount_uzs:
				self.paid_amount_usd = self.paid_amount_uzs / self.currency_exchange_rate
