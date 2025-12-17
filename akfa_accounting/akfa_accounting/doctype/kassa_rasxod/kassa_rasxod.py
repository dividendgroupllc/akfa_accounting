# Copyright (c) 2025, Asadbek and contributors
# For license information, please see license.txt

"""
Kassa Rasxod DocType

Handles cash expense transactions with automatic Journal Entry creation.
Supports multiple transaction types:
- Расход (Expense)
- Подотчет приход/расход (Accountable person income/expense)
- Коплашга (Transfer)
"""

import frappe
from frappe.model.document import Document
from frappe import _
import json

from akfa_accounting.akfa_accounting.doctype.kassa_rasxod.journal_entry_creator import (
    JournalEntryCreator,
    cancel_linked_journal_entries
)


class KassaRasxod(Document):
    
    def validate(self):
        self._validate_currency_exchange_rate()
        self._calculate_item_amounts()
        self._validate_items()
    
    def on_submit(self):
        self._create_journal_entries()
    
    def on_cancel(self):
        cancel_linked_journal_entries(self.name)
    
    # ==================== Validation Methods ====================
    
    def _validate_currency_exchange_rate(self):
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
    
    def _calculate_item_amounts(self):
        """Calculate USD/UZS amounts based on mode of payment"""
        if not self.mode_of_payment or not self.currency_exchange_rate or not self.items_data:
            return
        
        try:
            items = json.loads(self.items_data)
        except (json.JSONDecodeError, TypeError):
            return
        
        # USD mode - only Наличный USD H
        is_usd_mode = self.mode_of_payment == "Наличный USD H"
        
        for item in items:
            if is_usd_mode:
                # USD mode - paid_amount_usd is entered directly, calculate UZS
                if item.get('paid_amount_usd'):
                    item['paid_amount_uzs'] = item['paid_amount_usd'] * self.currency_exchange_rate
            else:
                # UZS mode (Наличный UZS H, Перечисления UZS) - paid_amount_uzs is entered, calculate USD
                if item.get('paid_amount_uzs'):
                    item['paid_amount_usd'] = item['paid_amount_uzs'] / self.currency_exchange_rate
        
        self.items_data = json.dumps(items)
    
    def _validate_items(self):
        """Validate items based on transaction type"""
        if not self.items_data:
            return
        
        try:
            items = json.loads(self.items_data)
        except (json.JSONDecodeError, TypeError):
            frappe.throw(_("Invalid items data"))
            return
        
        for idx, item in enumerate(items, start=1):
            tip = item.get('rasxod_podochot')
            self._validate_item_by_type(item, idx, tip)
    
    def _validate_item_by_type(self, item, idx, tip):
        """Validate a single item based on its type"""
        validators = {
            "Расход": self._validate_rasxod_item,
            "Подотчет приход": self._validate_podochot_item,
            "Подотчет расход": self._validate_podochot_item,
            "Коплашга": self._validate_koplashga_item
        }
        
        validator = validators.get(tip)
        if validator:
            validator(item, idx, tip)
    
    def _validate_rasxod_item(self, item, idx, tip):
        """Validate Расход type item"""
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
        
        if not item.get('date'):
            frappe.throw(
                _("Row #{0}: Date is required for Расход").format(idx),
                title=_("Validation Error")
            )
    
    def _validate_podochot_item(self, item, idx, tip):
        """Validate Подотчет type item"""
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
    
    def _validate_koplashga_item(self, item, idx, tip):
        """Validate Коплашга type item"""
        has_party1 = item.get('party_type') and item.get('party')
        has_party2 = item.get('party_type_2') and item.get('party_2')
        
        if not has_party1 and not has_party2:
            frappe.throw(
                _("Row #{0}: At least one Party must be filled for Коплашга").format(idx),
                title=_("Validation Error")
            )
    
    # ==================== Journal Entry Creation ====================
    
    def _create_journal_entries(self):
        """Create Journal Entries for Rasxod items"""
        if not self.items_data:
            return
        
        try:
            items = json.loads(self.items_data)
        except (json.JSONDecodeError, TypeError):
            return
        
        je_creator = JournalEntryCreator(self)
        
        for idx, item in enumerate(items, start=1):
            if item.get('rasxod_podochot') != "Расход":
                continue
            
            je_creator.process_rasxod_item(item, idx)


# ==================== Whitelisted API Methods ====================

@frappe.whitelist()
def get_employees_by_group(employee_group):
    """Get employees belonging to an Employee Group"""
    if not employee_group:
        return []
    
    return frappe.db.sql("""
        SELECT employee, employee_name 
        FROM `tabEmployee Group Table` 
        WHERE parent = %s AND parenttype = 'Employee Group'
    """, employee_group, as_dict=True)


@frappe.whitelist()
def get_mode_of_payment_balance(mode_of_payment, posting_date=None):
    """Get account balance for Mode of Payment"""
    if not mode_of_payment:
        return 0
    
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
    
    from erpnext.accounts.utils import get_balance_on
    
    return get_balance_on(account=account, date=posting_date) or 0
