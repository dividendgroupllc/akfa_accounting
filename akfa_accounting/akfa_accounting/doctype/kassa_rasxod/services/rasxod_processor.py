# Copyright (c) 2025, Asadbek and contributors
# For license information, please see license.txt

"""
Rasxod Processor

Handles Rasxod (expense) Journal Entry creation including:
- Simple expense without party (tz-1/5)
- Expense with party same date (tz-2/6)
- Nachislenie (accrual) with/without party (tz-3/4, tz-7/8)
"""

import frappe
from frappe import _

from akfa_accounting.akfa_accounting.doctype.kassa_rasxod.services.base_je_creator import (
    BaseJECreator,
)
from akfa_accounting.akfa_accounting.doctype.kassa_rasxod.services.nachislenie_entries import (
    NachislenieMixin,
)


class RasxodProcessor(NachislenieMixin, BaseJECreator):
    """Processor for Rasxod (expense) Journal Entries"""

    def process_rasxod_item(self, item, idx):
        """Route rasxod item to appropriate handler based on date and party"""
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

        if str(item_date) == str(self.doc.posting_date):
            if has_party:
                return self._create_je_with_party(
                    expense_account, amount, usd_amount, expense_cost_center,
                    party_type, party, idx, izoh
                )
            return self._create_je_without_party(
                expense_account, amount, usd_amount, expense_cost_center, idx, izoh
            )
        else:
            if has_party:
                return self._create_nachislenie_with_party(
                    expense_account, amount, usd_amount, expense_cost_center,
                    party_type, party, item_date, idx, izoh
                )
            return self._create_nachislenie_without_party(
                expense_account, amount, usd_amount, expense_cost_center,
                item_date, idx, izoh
            )

    def _create_je_without_party(self, expense_account, amount, usd_amount,
                                  expense_cost_center, item_idx, izoh=''):
        """tz-1/5: 2-line JE - Credit Cash, Debit Expense"""
        je = self._create_journal_entry()
        je.user_remark = f"Auto-created from Kassa Rasxod {self.doc.name}, Row #{item_idx}. {izoh}"

        self._add_account_entry(je, self.cash_account, credit=amount)
        self._add_account_entry(je, expense_account, debit=usd_amount,
                                cost_center=expense_cost_center, use_usd_rate=True)

        je.insert()
        je.submit()
        frappe.msgprint(_("Journal Entry {0} created for Row #{1}").format(
            frappe.utils.get_link_to_form("Journal Entry", je.name), item_idx))
        return je.name

    def _create_je_with_party(self, expense_account, amount, usd_amount,
                               expense_cost_center, party_type, party, item_idx, izoh=''):
        """tz-2/6: 4-line JE - Credit Payable, Debit Cash, Credit Cash, Debit Expense"""
        je = self._create_journal_entry()
        je.user_remark = f"Auto-created from Kassa Rasxod {self.doc.name}, Row #{item_idx}. {izoh}"

        self._add_account_entry(je, self.default_payable_account, credit=amount,
                                party_type=party_type, party=party)
        self._add_account_entry(je, self.cash_account, debit=amount)
        self._add_account_entry(je, self.cash_account, credit=amount)
        self._add_account_entry(je, expense_account, debit=usd_amount,
                                cost_center=expense_cost_center, use_usd_rate=True)

        je.insert()
        je.submit()
        frappe.msgprint(_("Journal Entry {0} created for Row #{1} with Party {2}").format(
            frappe.utils.get_link_to_form("Journal Entry", je.name), item_idx, party))
        return je.name

    def _create_nachislenie_with_party(self, expense_account, amount, usd_amount,
                                        expense_cost_center, party_type, party,
                                        item_date, item_idx, izoh=''):
        """Nachislenie WITH Party - Create 2 JEs"""
        nachislenie_supplier = self._get_nachislenie_supplier()

        # JE-1: Payment on posting_date (4 rows)
        je1 = self._create_journal_entry()
        je1.user_remark = f"Payment - Auto-created from Kassa Rasxod {self.doc.name}, Row #{item_idx}. {izoh}"
        self._add_nachislenie_payment_entries_with_party(je1, amount, party_type, party, nachislenie_supplier)
        je1.insert()
        je1.submit()

        # JE-2: Accrual on item_date (2 rows)
        je2 = self._create_journal_entry(item_date)
        je2.user_remark = f"Accrual - Auto-created from Kassa Rasxod {self.doc.name}, Row #{item_idx}. {izoh}"
        self._add_nachislenie_accrual_entries(je2, amount, usd_amount, expense_account,
                                               expense_cost_center, nachislenie_supplier)
        je2.insert()
        je2.submit()

        frappe.msgprint(
            _("Nachislenie with Party: 2 JEs for Row #{0}:<br>Payment: {1}<br>Accrual: {2}").format(
                item_idx,
                frappe.utils.get_link_to_form("Journal Entry", je1.name),
                frappe.utils.get_link_to_form("Journal Entry", je2.name)))
        return je1.name, je2.name

    def _create_nachislenie_without_party(self, expense_account, amount, usd_amount,
                                           expense_cost_center, item_date, item_idx, izoh=''):
        """Nachislenie WITHOUT Party - Create 2 JEs"""
        nachislenie_supplier = self._get_nachislenie_supplier()

        # JE-1: Payment on posting_date (2 rows)
        je1 = self._create_journal_entry()
        je1.user_remark = f"Payment - Auto-created from Kassa Rasxod {self.doc.name}, Row #{item_idx}. {izoh}"
        self._add_nachislenie_payment_entries_without_party(je1, amount, nachislenie_supplier)
        je1.insert()
        je1.submit()

        # JE-2: Accrual on item_date (2 rows)
        je2 = self._create_journal_entry(item_date)
        je2.user_remark = f"Accrual - Auto-created from Kassa Rasxod {self.doc.name}, Row #{item_idx}. {izoh}"
        self._add_nachislenie_accrual_entries(je2, amount, usd_amount, expense_account,
                                               expense_cost_center, nachislenie_supplier)
        je2.insert()
        je2.submit()

        frappe.msgprint(
            _("Nachislenie: 2 JEs for Row #{0}:<br>Payment: {1}<br>Accrual: {2}").format(
                item_idx,
                frappe.utils.get_link_to_form("Journal Entry", je1.name),
                frappe.utils.get_link_to_form("Journal Entry", je2.name)))
        return je1.name, je2.name
