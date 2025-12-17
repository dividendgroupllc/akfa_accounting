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
- tz-7: Nachislenie without Party (date < posting_date) - 2 JEs with system nachislenie party
- tz-8: Nachislenie with Party (date < posting_date) - 2 JEs (JE2 has 4 lines)
"""

import frappe
from frappe import _


class JournalEntryCreator:
    """Creates Journal Entries based on Kassa Rasxod transactions"""
    
    # Currency mode constants
    USD_MODE = "Наличный USD H"
    UZS_CASH_MODE = "Наличный UZS H"
    UZS_TRANSFER_MODE = "Перечисление UZS"
    
    # System parties for nachislenie
    NACHISLENIE_PARTY_USD = "Nachisleniya uchun USD"
    NACHISLENIE_PARTY_UZS = "Nachisleniya uchun UZS"
    
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
        self.exchange_rate = self.doc.currency_exchange_rate or 1
        
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
    
    def _get_nachislenie_party(self):
        """Get system party for nachislenie based on currency"""
        return self.NACHISLENIE_PARTY_UZS if self.is_multi_currency else self.NACHISLENIE_PARTY_USD
    
    def _get_amount(self, item):
        """Get amount based on currency mode"""
        if self.is_multi_currency:
            return item.get('paid_amount_uzs') or 0
        else:
            return item.get('paid_amount_usd') or 0
    
    def _get_usd_amount(self, item):
        """Get USD equivalent amount"""
        return item.get('paid_amount_usd') or 0
    
    def process_rasxod_item(self, item, idx):
        """Process a single Rasxod item and create appropriate Journal Entries"""
        item_date = item.get('date')
        party_type = item.get('party_type')
        party = item.get('party')
        has_party = bool(party_type and party)
        
        expense_account = item.get('category')
        if not expense_account:
            return
        
        amount = self._get_amount(item)
        usd_amount = self._get_usd_amount(item)
        if not amount and not usd_amount:
            return
        
        expense_cost_center = item.get('cost_center') or self.main_cost_center
        izoh = item.get('izoh', '')
        
        is_same_date = str(item_date) == str(self.doc.posting_date)
        
        if is_same_date:
            if has_party:
                # tz-2/6: With party, same date
                self._create_je_with_party_same_date(
                    expense_account, amount, usd_amount, expense_cost_center,
                    party_type, party, idx, izoh
                )
            else:
                # tz-1/5: Without party, same date
                self._create_je_without_party(
                    expense_account, amount, usd_amount, expense_cost_center,
                    idx, izoh
                )
        else:
            # Nachislenie - date < posting_date
            if self.is_multi_currency:
                if has_party:
                    # tz-8: UZS nachislenie with party
                    self._create_uzs_nachislenie_with_party(
                        expense_account, amount, usd_amount, expense_cost_center,
                        party_type, party, item_date, idx, izoh
                    )
                else:
                    # tz-7: UZS nachislenie without party
                    self._create_uzs_nachislenie_without_party(
                        expense_account, amount, usd_amount, expense_cost_center,
                        item_date, idx, izoh
                    )
            else:
                # tz-3/4: USD nachislenie
                self._create_usd_nachislenie(
                    expense_account, amount, usd_amount, expense_cost_center,
                    party_type, party, item_date, idx, izoh
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
        """tz-1/5: Create 2-line JE when Party is empty"""
        je = self._create_journal_entry(posting_date)
        je.user_remark = f"Auto-created from Kassa Rasxod {self.doc.name}, Row #{item_idx}. {izoh}"
        
        if self.is_multi_currency:
            je.append("accounts", {
                "account": self.cash_account,
                "credit_in_account_currency": amount,
                "debit_in_account_currency": 0,
                "exchange_rate": self.exchange_rate,
                "cost_center": self.main_cost_center
            })
            je.append("accounts", {
                "account": expense_account,
                "debit_in_account_currency": usd_amount,
                "credit_in_account_currency": 0,
                "exchange_rate": 1,
                "cost_center": expense_cost_center
            })
        else:
            je.append("accounts", {
                "account": self.cash_account,
                "credit_in_account_currency": amount,
                "debit_in_account_currency": 0,
                "cost_center": self.main_cost_center
            })
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
        return je.name
    
    def _create_je_with_party_same_date(self, expense_account, amount, usd_amount, expense_cost_center,
                                        party_type, party, item_idx, izoh=''):
        """tz-2/6: Create 4-line JE when Party is filled and date == posting_date"""
        je = self._create_journal_entry()
        je.user_remark = f"Auto-created from Kassa Rasxod {self.doc.name}, Row #{item_idx}. {izoh}"
        
        if self.is_multi_currency:
            # Row 1: Credit Payable with Party
            je.append("accounts", {
                "account": self.default_payable_account,
                "credit_in_account_currency": amount,
                "debit_in_account_currency": 0,
                "party_type": party_type,
                "party": party,
                "exchange_rate": self.exchange_rate,
                "cost_center": self.main_cost_center
            })
            # Row 2: Debit Cash
            je.append("accounts", {
                "account": self.cash_account,
                "debit_in_account_currency": amount,
                "credit_in_account_currency": 0,
                "exchange_rate": self.exchange_rate,
                "cost_center": self.main_cost_center
            })
            # Row 3: Credit Cash
            je.append("accounts", {
                "account": self.cash_account,
                "credit_in_account_currency": amount,
                "debit_in_account_currency": 0,
                "exchange_rate": self.exchange_rate,
                "cost_center": self.main_cost_center
            })
            # Row 4: Debit Expense
            je.append("accounts", {
                "account": expense_account,
                "debit_in_account_currency": usd_amount,
                "credit_in_account_currency": 0,
                "exchange_rate": 1,
                "cost_center": expense_cost_center
            })
        else:
            je.append("accounts", {
                "account": self.default_payable_account,
                "credit_in_account_currency": amount,
                "debit_in_account_currency": 0,
                "party_type": party_type,
                "party": party,
                "cost_center": self.main_cost_center
            })
            je.append("accounts", {
                "account": self.cash_account,
                "debit_in_account_currency": amount,
                "credit_in_account_currency": 0,
                "cost_center": self.main_cost_center
            })
            je.append("accounts", {
                "account": self.cash_account,
                "credit_in_account_currency": amount,
                "debit_in_account_currency": 0,
                "cost_center": self.main_cost_center
            })
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
        return je.name
    
    def _create_usd_nachislenie(self, expense_account, amount, usd_amount, expense_cost_center,
                                party_type, party, item_date, item_idx, izoh=''):
        """tz-3/4: USD Nachislenie - 2 separate JEs"""
        nachislenie_party = self._get_nachislenie_party()
        actual_party_type = party_type or "Supplier"
        actual_party = party or nachislenie_party
        
        # JE-1: Payment on posting_date
        je1 = self._create_journal_entry()
        je1.user_remark = f"Payment - Auto-created from Kassa Rasxod {self.doc.name}, Row #{item_idx}. {izoh}"
        
        je1.append("accounts", {
            "account": self.default_payable_account,
            "debit_in_account_currency": amount,
            "credit_in_account_currency": 0,
            "party_type": actual_party_type,
            "party": actual_party,
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
        
        # JE-2: Accrual on item_date
        je2 = self._create_journal_entry(item_date)
        je2.user_remark = f"Accrual - Auto-created from Kassa Rasxod {self.doc.name}, Row #{item_idx}. {izoh}"
        
        je2.append("accounts", {
            "account": self.default_payable_account,
            "credit_in_account_currency": amount,
            "debit_in_account_currency": 0,
            "party_type": actual_party_type,
            "party": actual_party,
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
    
    def _create_uzs_nachislenie_without_party(self, expense_account, amount, usd_amount, 
                                               expense_cost_center, item_date, item_idx, izoh=''):
        """
        tz-7: UZS Nachislenie without Party
        
        JE-1 on item_date (Accrual):
        - Credit 2111 (Nachisleniya uchun UZS) 
        - Debit Expense
        
        JE-2 on posting_date (Payment):
        - Credit Cash
        - Debit 2111 (Nachisleniya uchun UZS)
        """
        nachislenie_party = self._get_nachislenie_party()
        
        # JE-1: Accrual on item_date
        je1 = self._create_journal_entry(item_date)
        je1.user_remark = f"Accrual - Auto-created from Kassa Rasxod {self.doc.name}, Row #{item_idx}. {izoh}"
        
        je1.append("accounts", {
            "account": self.default_payable_account,
            "credit_in_account_currency": amount,
            "debit_in_account_currency": 0,
            "party_type": "Supplier",
            "party": nachislenie_party,
            "exchange_rate": self.exchange_rate,
            "cost_center": self.main_cost_center
        })
        je1.append("accounts", {
            "account": expense_account,
            "debit_in_account_currency": usd_amount,
            "credit_in_account_currency": 0,
            "exchange_rate": 1,
            "cost_center": expense_cost_center
        })
        
        je1.insert()
        je1.submit()
        
        # JE-2: Payment on posting_date
        je2 = self._create_journal_entry()
        je2.user_remark = f"Payment - Auto-created from Kassa Rasxod {self.doc.name}, Row #{item_idx}. {izoh}"
        
        je2.append("accounts", {
            "account": self.cash_account,
            "credit_in_account_currency": amount,
            "debit_in_account_currency": 0,
            "exchange_rate": self.exchange_rate,
            "cost_center": self.main_cost_center
        })
        je2.append("accounts", {
            "account": self.default_payable_account,
            "debit_in_account_currency": amount,
            "credit_in_account_currency": 0,
            "party_type": "Supplier",
            "party": nachislenie_party,
            "exchange_rate": self.exchange_rate,
            "cost_center": self.main_cost_center
        })
        
        je2.insert()
        je2.submit()
        
        frappe.msgprint(
            _("UZS Nachislenie: 2 Journal Entries created for Row #{0}:<br>"
              "Accrual JE: {1} (Date: {2})<br>"
              "Payment JE: {3} (Date: {4})").format(
                item_idx,
                frappe.utils.get_link_to_form("Journal Entry", je1.name),
                item_date,
                frappe.utils.get_link_to_form("Journal Entry", je2.name),
                self.doc.posting_date
            )
        )
        return je1.name, je2.name
    
    def _create_uzs_nachislenie_with_party(self, expense_account, amount, usd_amount,
                                           expense_cost_center, party_type, party,
                                           item_date, item_idx, izoh=''):
        """
        tz-8: UZS Nachislenie with Party
        
        JE-1 on item_date (Accrual) - 2 lines:
        - Debit 2111 (Nachisleniya uchun UZS)
        - Credit Cash
        
        JE-2 on posting_date (Payment + Transfer) - 4 lines:
        - Credit 2111 (actual party - Sektor alumin)
        - Debit Cash
        - Credit Cash  
        - Debit 2111 (Nachisleniya uchun UZS)
        """
        nachislenie_party = self._get_nachislenie_party()
        
        # JE-1: Accrual on item_date
        je1 = self._create_journal_entry(item_date)
        je1.user_remark = f"Accrual - Auto-created from Kassa Rasxod {self.doc.name}, Row #{item_idx}. {izoh}"
        
        je1.append("accounts", {
            "account": self.default_payable_account,
            "debit_in_account_currency": amount,
            "credit_in_account_currency": 0,
            "party_type": "Supplier",
            "party": nachislenie_party,
            "exchange_rate": self.exchange_rate,
            "cost_center": self.main_cost_center
        })
        je1.append("accounts", {
            "account": self.cash_account,
            "credit_in_account_currency": amount,
            "debit_in_account_currency": 0,
            "exchange_rate": self.exchange_rate,
            "cost_center": self.main_cost_center
        })
        
        je1.insert()
        je1.submit()
        
        # JE-2: Payment on posting_date - 4 lines
        je2 = self._create_journal_entry()
        je2.user_remark = f"Payment - Auto-created from Kassa Rasxod {self.doc.name}, Row #{item_idx}. {izoh}"
        
        # Row 1: Credit Payable (actual party)
        je2.append("accounts", {
            "account": self.default_payable_account,
            "credit_in_account_currency": amount,
            "debit_in_account_currency": 0,
            "party_type": party_type,
            "party": party,
            "exchange_rate": self.exchange_rate,
            "cost_center": self.main_cost_center
        })
        # Row 2: Debit Cash
        je2.append("accounts", {
            "account": self.cash_account,
            "debit_in_account_currency": amount,
            "credit_in_account_currency": 0,
            "exchange_rate": self.exchange_rate,
            "cost_center": self.main_cost_center
        })
        # Row 3: Credit Cash
        je2.append("accounts", {
            "account": self.cash_account,
            "credit_in_account_currency": amount,
            "debit_in_account_currency": 0,
            "exchange_rate": self.exchange_rate,
            "cost_center": self.main_cost_center
        })
        # Row 4: Debit Payable (nachislenie party)
        je2.append("accounts", {
            "account": self.default_payable_account,
            "debit_in_account_currency": amount,
            "credit_in_account_currency": 0,
            "party_type": "Supplier",
            "party": nachislenie_party,
            "exchange_rate": self.exchange_rate,
            "cost_center": self.main_cost_center
        })
        
        je2.insert()
        je2.submit()
        
        frappe.msgprint(
            _("UZS Nachislenie with Party: 2 Journal Entries created for Row #{0}:<br>"
              "Accrual JE: {1} (Date: {2})<br>"
              "Payment JE: {3} (Date: {4})").format(
                item_idx,
                frappe.utils.get_link_to_form("Journal Entry", je1.name),
                item_date,
                frappe.utils.get_link_to_form("Journal Entry", je2.name),
                self.doc.posting_date
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
