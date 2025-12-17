# Copyright (c) 2025, Asadbek and contributors
# For license information, please see license.txt

"""
Journal Entry Creator for Kassa Rasxod

This module handles automatic Journal Entry creation for different scenarios:

USD Mode (Наличный USD H):
- tz-1: Rasxod without Party (date == posting_date) - 2 line JE
- tz-2: Rasxod with Party (date == posting_date) - 4 line JE
- tz-3/4: Nachislenie - Rasxod with Party (date < posting_date) - 2 separate JEs

UZS Mode (Наличный UZS H):
- tz-5: Rasxod without Party (date == posting_date) - 2 line JE, Multi Currency
- tz-6: Rasxod with Party (date == posting_date) - 4 line JE, Multi Currency
"""

import frappe
from frappe import _


class JournalEntryCreator:
    """Creates Journal Entries based on Kassa Rasxod transactions"""
    
    # Currency mode constants
    USD_MODE = "Наличный USD H"
    UZS_CASH_MODE = "Наличный UZS H"
    UZS_TRANSFER_MODE = "Перечисления UZS"
    
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
        # Get cash account from Mode of Payment
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
        
        # Get account currency
        self.cash_account_currency = frappe.db.get_value(
            "Account", self.cash_account, "account_currency"
        )
        
        # Determine if multi-currency mode
        self.is_multi_currency = self.cash_account_currency == "UZS"
        
        # For UZS accounts, exchange_rate should be UZS to USD (1/12020 = 0.000083)
        # For USD accounts, exchange_rate = 1
        usd_to_uzs_rate = self.doc.currency_exchange_rate or 12020
        if self.is_multi_currency:
            # UZS mode: exchange_rate = 1 UZS = X USD
            self.exchange_rate = 1 / usd_to_uzs_rate
        else:
            # USD mode: exchange_rate = 1
            self.exchange_rate = 1
        
        # Get company from account
        self.company = frappe.db.get_value("Account", self.cash_account, "company")
        
        # Get default payable account based on currency
        if self.is_multi_currency:
            # UZS mode - use UZS payable account (2111)
            self.default_payable_account = frappe.db.get_value(
                "Account",
                {"account_currency": "UZS", "account_type": "Payable", "company": self.company},
                "name"
            ) or "2111 - Creditors UZS - A"
        else:
            # USD mode - use USD payable account (2110)
            self.default_payable_account = frappe.db.get_value(
                "Company", self.company, "default_payable_account"
            )
        
        # Main cost center for Cash/Payable accounts
        self.main_cost_center = (
            frappe.db.get_value("Company", self.company, "cost_center") 
            or "Main - A"
        )
    
    def _get_amount(self, item):
        """Get amount based on currency mode"""
        if self.is_multi_currency:
            # UZS mode - return UZS amount
            return item.get('paid_amount_uzs') or 0
        else:
            # USD mode - return USD amount
            return item.get('paid_amount_usd') or 0
    
    def _get_usd_amount(self, item):
        """Get USD equivalent amount"""
        return item.get('paid_amount_usd') or 0
    
    def process_rasxod_item(self, item, idx):
        """
        Process a single Rasxod item and create appropriate Journal Entries
        
        Cases:
        - date == posting_date, no party: tz-1/5 (2-line JE)
        - date == posting_date, with party: tz-2/6 (4-line JE)
        - date < posting_date, with party: tz-3/4 Nachislenie (2 separate JEs)
        """
        item_date = item.get('date')
        party_type = item.get('party_type')
        party = item.get('party')
        has_party = bool(party_type and party)
        
        # Get expense account and cost center
        expense_account = item.get('category')
        if not expense_account:
            return
        
        amount = self._get_amount(item)
        usd_amount = self._get_usd_amount(item)
        if not amount and not usd_amount:
            return
        
        expense_cost_center = item.get('cost_center') or self.main_cost_center
        izoh = item.get('izoh', '')
        
        # Determine which case
        if str(item_date) == str(self.doc.posting_date):
            # Date matches posting date
            if has_party:
                # tz-2/6: With party, same date
                self._create_je_with_party_same_date(
                    expense_account=expense_account,
                    amount=amount,
                    usd_amount=usd_amount,
                    expense_cost_center=expense_cost_center,
                    party_type=party_type,
                    party=party,
                    item_idx=idx,
                    izoh=izoh
                )
            else:
                # tz-1/5: Without party
                self._create_je_without_party(
                    expense_account=expense_account,
                    amount=amount,
                    usd_amount=usd_amount,
                    expense_cost_center=expense_cost_center,
                    item_idx=idx,
                    izoh=izoh
                )
        else:
            # Date is different (past date) - Nachislenie
            if has_party:
                # tz-3/4: Nachislenie with party
                self._create_nachislenie_entries(
                    expense_account=expense_account,
                    amount=amount,
                    usd_amount=usd_amount,
                    expense_cost_center=expense_cost_center,
                    party_type=party_type,
                    party=party,
                    item_date=item_date,
                    item_idx=idx,
                    izoh=izoh
                )
            else:
                # Without party but different date - just create expense entry on item date
                self._create_je_without_party(
                    expense_account=expense_account,
                    amount=amount,
                    usd_amount=usd_amount,
                    expense_cost_center=expense_cost_center,
                    item_idx=idx,
                    izoh=izoh,
                    posting_date=item_date
                )
    
    def _create_journal_entry(self, posting_date=None):
        """Create base Journal Entry document"""
        je = frappe.new_doc("Journal Entry")
        je.voucher_type = "Journal Entry"
        je.posting_date = posting_date or self.doc.posting_date
        je.company = self.company
        
        if self.is_multi_currency:
            je.multi_currency = 1
        
        return je
    
    def _create_je_without_party(self, expense_account, amount, usd_amount, expense_cost_center, 
                                  item_idx, izoh='', posting_date=None):
        """
        tz-1 (USD) / tz-5 (UZS): Create Journal Entry when Party is empty
        
        Entries:
        - Credit: Cash Account (1112/1113) → Main cost center
        - Debit: Expense Account (5209) → Expense cost center
        """
        je = self._create_journal_entry(posting_date)
        je.user_remark = f"Auto-created from Kassa Rasxod {self.doc.name}, Row #{item_idx}. {izoh}"
        
        if self.is_multi_currency:
            # UZS mode - amounts in account currency (UZS), with exchange rate
            # Row 1: Credit Cash Account (UZS)
            je.append("accounts", {
                "account": self.cash_account,
                "credit_in_account_currency": amount,
                "debit_in_account_currency": 0,
                "exchange_rate": self.exchange_rate,
                "cost_center": self.main_cost_center
            })
            
            # Row 2: Debit Expense Account (USD account, but entry in USD equivalent)
            je.append("accounts", {
                "account": expense_account,
                "debit_in_account_currency": usd_amount,
                "credit_in_account_currency": 0,
                "exchange_rate": 1,
                "cost_center": expense_cost_center
            })
        else:
            # USD mode - simple USD amounts
            # Row 1: Credit Cash Account
            je.append("accounts", {
                "account": self.cash_account,
                "credit_in_account_currency": amount,
                "debit_in_account_currency": 0,
                "cost_center": self.main_cost_center
            })
            
            # Row 2: Debit Expense Account
            je.append("accounts", {
                "account": expense_account,
                "debit_in_account_currency": amount,
                "credit_in_account_currency": 0,
                "cost_center": expense_cost_center
            })
        
        je.insert()
        je.submit()
        
        frappe.msgprint(
            _("Journal Entry {0} created for Row #{1}").format(
                frappe.utils.get_link_to_form("Journal Entry", je.name), 
                item_idx
            )
        )
        
        return je.name
    
    def _create_je_with_party_same_date(self, expense_account, amount, usd_amount, expense_cost_center,
                                        party_type, party, item_idx, izoh=''):
        """
        tz-2 (USD) / tz-6 (UZS): Create Journal Entry when Party is filled and date == posting_date
        
        Entries (4 lines):
        - Row 1: Credit Payable (2110/2111) with Party → Main cost center
        - Row 2: Debit Cash (1112/1113) → Main cost center
        - Row 3: Credit Cash (1112/1113) → Main cost center
        - Row 4: Debit Expense (5209) → Expense cost center
        """
        je = self._create_journal_entry()
        je.user_remark = f"Auto-created from Kassa Rasxod {self.doc.name}, Row #{item_idx}. {izoh}"
        
        if self.is_multi_currency:
            # UZS mode with multi-currency
            
            # Row 1: Credit Payable with Party (UZS)
            je.append("accounts", {
                "account": self.default_payable_account,
                "credit_in_account_currency": amount,
                "debit_in_account_currency": 0,
                "party_type": party_type,
                "party": party,
                "exchange_rate": self.exchange_rate,
                "cost_center": self.main_cost_center
            })
            
            # Row 2: Debit Cash (payment to party) - UZS
            je.append("accounts", {
                "account": self.cash_account,
                "debit_in_account_currency": amount,
                "credit_in_account_currency": 0,
                "exchange_rate": self.exchange_rate,
                "cost_center": self.main_cost_center
            })
            
            # Row 3: Credit Cash (expense payment) - UZS
            je.append("accounts", {
                "account": self.cash_account,
                "credit_in_account_currency": amount,
                "debit_in_account_currency": 0,
                "exchange_rate": self.exchange_rate,
                "cost_center": self.main_cost_center
            })
            
            # Row 4: Debit Expense (USD account)
            je.append("accounts", {
                "account": expense_account,
                "debit_in_account_currency": usd_amount,
                "credit_in_account_currency": 0,
                "exchange_rate": 1,
                "cost_center": expense_cost_center
            })
        else:
            # USD mode - simple
            
            # Row 1: Credit Payable with Party
            je.append("accounts", {
                "account": self.default_payable_account,
                "credit_in_account_currency": amount,
                "debit_in_account_currency": 0,
                "party_type": party_type,
                "party": party,
                "cost_center": self.main_cost_center
            })
            
            # Row 2: Debit Cash (payment to party)
            je.append("accounts", {
                "account": self.cash_account,
                "debit_in_account_currency": amount,
                "credit_in_account_currency": 0,
                "cost_center": self.main_cost_center
            })
            
            # Row 3: Credit Cash (expense payment)
            je.append("accounts", {
                "account": self.cash_account,
                "credit_in_account_currency": amount,
                "debit_in_account_currency": 0,
                "cost_center": self.main_cost_center
            })
            
            # Row 4: Debit Expense
            je.append("accounts", {
                "account": expense_account,
                "debit_in_account_currency": amount,
                "credit_in_account_currency": 0,
                "cost_center": expense_cost_center
            })
        
        je.insert()
        je.submit()
        
        frappe.msgprint(
            _("Journal Entry {0} created for Row #{1} with Party {2}").format(
                frappe.utils.get_link_to_form("Journal Entry", je.name), 
                item_idx, 
                party
            )
        )
        
        return je.name
    
    def _create_nachislenie_entries(self, expense_account, amount, usd_amount, expense_cost_center,
                                    party_type, party, item_date, item_idx, izoh=''):
        """
        tz-3/4: Nachislenie - Create 2 Journal Entries when Party filled and date < posting_date
        
        JE-1 on posting_date (payment):
        - Row 1: Debit Payable (2110/2111) with Party → Main cost center
        - Row 2: Credit Cash (1112/1113) → Main cost center
        
        JE-2 on item_date (expense accrual):
        - Row 1: Credit Payable (2110/2111) with Party → Main cost center
        - Row 2: Debit Expense (5207) → Expense cost center
        """
        # JE-1: Payment entry on posting_date
        je1 = self._create_journal_entry()
        je1.user_remark = f"Payment - Auto-created from Kassa Rasxod {self.doc.name}, Row #{item_idx}. {izoh}"
        
        if self.is_multi_currency:
            # Debit Payable (clearing the liability) - UZS
            je1.append("accounts", {
                "account": self.default_payable_account,
                "debit_in_account_currency": amount,
                "credit_in_account_currency": 0,
                "party_type": party_type,
                "party": party,
                "exchange_rate": self.exchange_rate,
                "cost_center": self.main_cost_center
            })
            
            # Credit Cash (payment out) - UZS
            je1.append("accounts", {
                "account": self.cash_account,
                "credit_in_account_currency": amount,
                "debit_in_account_currency": 0,
                "exchange_rate": self.exchange_rate,
                "cost_center": self.main_cost_center
            })
        else:
            # USD mode
            je1.append("accounts", {
                "account": self.default_payable_account,
                "debit_in_account_currency": amount,
                "credit_in_account_currency": 0,
                "party_type": party_type,
                "party": party,
                "cost_center": self.main_cost_center
            })
            
            je1.append("accounts", {
                "account": self.cash_account,
                "credit_in_account_currency": amount,
                "debit_in_account_currency": 0,
                "cost_center": self.main_cost_center
            })
        
        je1.insert()
        je1.submit()
        
        # JE-2: Expense accrual on item_date
        je2 = self._create_journal_entry(item_date)
        je2.user_remark = f"Accrual - Auto-created from Kassa Rasxod {self.doc.name}, Row #{item_idx}. {izoh}"
        
        if self.is_multi_currency:
            # Credit Payable (creating liability) - UZS
            je2.append("accounts", {
                "account": self.default_payable_account,
                "credit_in_account_currency": amount,
                "debit_in_account_currency": 0,
                "party_type": party_type,
                "party": party,
                "exchange_rate": self.exchange_rate,
                "cost_center": self.main_cost_center
            })
            
            # Debit Expense - USD account
            je2.append("accounts", {
                "account": expense_account,
                "debit_in_account_currency": usd_amount,
                "credit_in_account_currency": 0,
                "exchange_rate": 1,
                "cost_center": expense_cost_center
            })
        else:
            # USD mode
            je2.append("accounts", {
                "account": self.default_payable_account,
                "credit_in_account_currency": amount,
                "debit_in_account_currency": 0,
                "party_type": party_type,
                "party": party,
                "cost_center": self.main_cost_center
            })
            
            je2.append("accounts", {
                "account": expense_account,
                "debit_in_account_currency": amount,
                "credit_in_account_currency": 0,
                "cost_center": expense_cost_center
            })
        
        je2.insert()
        je2.submit()
        
        frappe.msgprint(
            _("Nachislenie: 2 Journal Entries created for Row #{0}:<br>"
              "Payment JE: {1} (Date: {2})<br>"
              "Accrual JE: {3} (Date: {4})").format(
                item_idx,
                frappe.utils.get_link_to_form("Journal Entry", je1.name),
                self.doc.posting_date,
                frappe.utils.get_link_to_form("Journal Entry", je2.name),
                item_date
            )
        )
        
        return je1.name, je2.name


def cancel_linked_journal_entries(kassa_rasxod_name):
    """Cancel all Journal Entries linked to a Kassa Rasxod document"""
    journal_entries = frappe.get_all(
        "Journal Entry",
        filters={
            "user_remark": ["like", f"%Kassa Rasxod {kassa_rasxod_name}%"],
            "docstatus": 1
        },
        pluck="name"
    )
    
    for je_name in journal_entries:
        je = frappe.get_doc("Journal Entry", je_name)
        je.cancel()
        frappe.msgprint(_("Journal Entry {0} cancelled").format(je_name))
