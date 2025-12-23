# Copyright (c) 2025, Asadbek and contributors
# For license information, please see license.txt

"""
Base Journal Entry Creator

Contains base class with initialization, setup, and utility methods
for all Journal Entry processors.
"""

import frappe
from frappe import _


class BaseJECreator:
    """Base class for Journal Entry creation with shared setup and utilities"""

    # Currency mode constants
    USD_MODE = "Наличный USD H"
    UZS_CASH_MODE = "Наличный UZS H"
    UZS_TRANSFER_MODE = "Перечисления UZS"

    # Nachislenie supplier constants
    NACHISLENIE_SUPPLIER_USD = "Nachisleniya uchun USD"
    NACHISLENIE_SUPPLIER_UZS = "Nachisleniya uchun UZS"

    def __init__(self, kassa_rasxod_doc):
        self.doc = kassa_rasxod_doc
        self.company = None
        self.cash_account = None
        self.cash_account_currency = None
        self.default_payable_account = None
        self.main_cost_center = None
        self.is_multi_currency = False
        self.exchange_rate = None
        self._setup()

    def _setup(self):
        """Initialize accounts and cost centers"""
        self._setup_cash_account()
        self._setup_currency_mode()
        self._setup_company_defaults()

    def _setup_cash_account(self):
        """Get cash account from Mode of Payment"""
        self.cash_account = frappe.db.get_value(
            "Mode of Payment Account",
            {
                "parent": self.doc.mode_of_payment,
                "parenttype": "Mode of Payment"
            },
            "default_account"
        )

        if not self.cash_account:
            frappe.throw(
                _("No default account found for Mode of Payment: {0}").format(
                    self.doc.mode_of_payment
                )
            )

        self.cash_account_currency = frappe.db.get_value(
            "Account", self.cash_account, "account_currency"
        )

    def _setup_currency_mode(self):
        """Determine if multi-currency mode and set exchange rate"""
        self.is_multi_currency = self.cash_account_currency == "UZS"

        usd_to_uzs_rate = self.doc.currency_exchange_rate or 12020
        if self.is_multi_currency:
            self.exchange_rate = 1 / usd_to_uzs_rate
        else:
            self.exchange_rate = 1

    def _setup_company_defaults(self):
        """Get company, payable account, and cost center"""
        self.company = frappe.db.get_value("Account", self.cash_account, "company")

        if self.is_multi_currency:
            self.default_payable_account = frappe.db.get_value(
                "Account",
                {"account_currency": "UZS", "account_type": "Payable", "company": self.company},
                "name"
            ) or "2111 - Creditors UZS - A"
        else:
            self.default_payable_account = frappe.db.get_value(
                "Company", self.company, "default_payable_account"
            )

        self.main_cost_center = (
            frappe.db.get_value("Company", self.company, "cost_center")
            or "Main - A"
        )

    def _get_amount(self, item):
        """Get amount based on currency mode"""
        if self.is_multi_currency:
            return item.get('paid_amount_uzs') or 0
        else:
            return item.get('paid_amount_usd') or 0

    def _get_usd_amount(self, item):
        """Get USD equivalent amount"""
        return item.get('paid_amount_usd') or 0

    def _create_journal_entry(self, posting_date=None):
        """Create base Journal Entry document"""
        je = frappe.new_doc("Journal Entry")
        je.voucher_type = "Journal Entry"
        je.posting_date = posting_date or self.doc.posting_date
        je.company = self.company

        if self.is_multi_currency:
            je.multi_currency = 1

        return je

    def _get_nachislenie_supplier(self):
        """Get appropriate Nachislenie supplier based on currency mode"""
        return (
            self.NACHISLENIE_SUPPLIER_UZS if self.is_multi_currency
            else self.NACHISLENIE_SUPPLIER_USD
        )

    def _add_account_entry(self, je, account, debit=0, credit=0, party_type=None,
                           party=None, cost_center=None, use_usd_rate=False):
        """Add account entry with proper multi-currency handling"""
        entry = {
            "account": account,
            "debit_in_account_currency": debit,
            "credit_in_account_currency": credit,
            "cost_center": cost_center or self.main_cost_center
        }

        if party_type and party:
            entry["party_type"] = party_type
            entry["party"] = party

        if self.is_multi_currency:
            entry["exchange_rate"] = 1 if use_usd_rate else self.exchange_rate

        je.append("accounts", entry)
