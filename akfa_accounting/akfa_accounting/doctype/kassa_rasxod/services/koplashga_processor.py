# Copyright (c) 2025, Asadbek and contributors
# For license information, please see license.txt

"""
Koplashga Processor

Handles Koplashga (transfer between parties via cash) Journal Entry creation.
Supports single party and dual party transfers.
"""

import frappe
from frappe import _

from akfa_accounting.akfa_accounting.doctype.kassa_rasxod.services.base_je_creator import (
    BaseJECreator,
)


class KoplashgaProcessor(BaseJECreator):
    """Processor for Koplashga Journal Entries"""

    def process_koplashga_item(self, item, idx):
        """Process Koplashga item - Transfer between parties via cash"""
        party_type = item.get('party_type')
        party = item.get('party')
        party_type_2 = item.get('party_type_2')
        party_2 = item.get('party_2')

        has_party1 = bool(party_type and party)
        has_party2 = bool(party_type_2 and party_2)

        amount = self._get_amount(item)
        if not amount and not self._get_usd_amount(item):
            return

        izoh = item.get('izoh', '')

        if has_party1 and has_party2:
            return self._create_both_parties_je(
                party_type, party, party_type_2, party_2, amount, idx, izoh
            )
        elif has_party1:
            return self._create_single_party_je(party_type, party, amount, idx, izoh)

    def _create_single_party_je(self, party_type, party, amount, item_idx, izoh=''):
        """Create 2-line JE: Credit Cash, Debit Payable with Party"""
        je = self._create_journal_entry()
        je.user_remark = f"Koplashga - Auto-created from Kassa Rasxod {self.doc.name}, Row #{item_idx}. {izoh}"

        # Credit Cash (money goes out)
        self._add_account_entry(je, self.cash_account, credit=amount)
        # Debit Payable with Party
        self._add_account_entry(je, self.default_payable_account, debit=amount,
                                party_type=party_type, party=party)

        je.insert()
        je.submit()

        frappe.msgprint(
            _("Journal Entry {0} created for Koplashga Row #{1}, Party {2}").format(
                frappe.utils.get_link_to_form("Journal Entry", je.name), item_idx, party
            )
        )
        return je.name

    def _create_both_parties_je(self, party_type_1, party_1, party_type_2, party_2,
                                 amount, item_idx, izoh=''):
        """Create 4-line JE for transfer between two parties via cash"""
        je = self._create_journal_entry()
        je.user_remark = f"Koplashga Transfer - Auto-created from Kassa Rasxod {self.doc.name}, Row #{item_idx}. {izoh}"

        # Row 1: Credit Payable with Party 2 (receiver)
        self._add_account_entry(je, self.default_payable_account, credit=amount,
                                party_type=party_type_2, party=party_2)
        # Row 2: Debit Cash (money comes in)
        self._add_account_entry(je, self.cash_account, debit=amount)
        # Row 3: Credit Cash (money goes out)
        self._add_account_entry(je, self.cash_account, credit=amount)
        # Row 4: Debit Payable with Party 1 (sender)
        self._add_account_entry(je, self.default_payable_account, debit=amount,
                                party_type=party_type_1, party=party_1)

        je.insert()
        je.submit()

        frappe.msgprint(
            _("Journal Entry {0} created for Koplashga Transfer Row #{1}: {2} -> {3}").format(
                frappe.utils.get_link_to_form("Journal Entry", je.name), item_idx, party_1, party_2
            )
        )
        return je.name
