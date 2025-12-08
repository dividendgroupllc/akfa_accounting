"""
Payment Entry Utilities
Helper functions for Payment Entry automation
"""

import frappe
from frappe import _

# Account mappings - hardcoded based on database structure
ACCOUNT_MAPPINGS = {
	"USD": {
		"azimov": "1110 - Наличные USD Azimov - A",
		"hamidulla": "1112 - Наличные USD Hamidulla - A",
		"aripov": "1114 - Наличные USD Aripov - A"
	},
	"UZS": {
		"azimov": "1111 - Наличные UZS Azimov - A",
		"hamidulla": "1113 - Наличные UZS Hamidulla - A",
		"aripov": "1115 - Наличные UZS Aripov - A"
	}
}

# Supplier mappings for Ofis GL
OFIS_GL_SUPPLIERS = {
	"USD": "Ofis GL USD",
	"UZS": "Ofis GL UZS"
}

# Mode of Payment names
MODE_OF_PAYMENT = {
	"CASH_USD": "Наличные USD",
	"CASH_UZS": "Наличные UZS",
	"EXCHANGE_USD_TO_UZS": "Обмен USD to UZS",
	"EXCHANGE_UZS_TO_USD": "Обмен UZS to USD",
	"TRANSFER_USD": "Перемещения на USD",
	"TRANSFER_UZS": "Перемещения на UZS"
}


def get_account_by_company(account_name, company):
	"""Get account name filtered by company"""
	if not company:
		return account_name
	
	# Account name already includes company suffix, just verify it exists
	account = frappe.db.get_value(
		"Account",
		{"name": account_name, "company": company},
		"name"
	)
	return account


def get_account_balance(account, date, company=None):
	"""Get account balance on a specific date"""
	if not account or not date:
		return 0
	
	try:
		from erpnext.accounts.utils import get_balance_on
		balance = get_balance_on(account=account, date=date)
		return balance or 0
	except Exception as e:
		frappe.log_error(f"Error getting balance for {account}: {str(e)}")
		return 0


def get_currency_from_mode_of_payment(mode_of_payment):
	"""Determine currency from Mode of Payment name"""
	if not mode_of_payment:
		return None
	
	if "USD" in mode_of_payment:
		return "USD"
	elif "UZS" in mode_of_payment:
		return "UZS"
	
	return None

