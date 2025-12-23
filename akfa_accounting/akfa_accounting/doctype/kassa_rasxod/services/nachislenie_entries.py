# Copyright (c) 2025, Asadbek and contributors
# For license information, please see license.txt

"""
Nachislenie Entry Helpers

Contains helper methods for adding Nachislenie-specific Journal Entry rows.
Used by RasxodProcessor for accrual accounting entries.
"""


class NachislenieMixin:
    """Mixin class providing nachislenie entry creation methods"""

    def _add_nachislenie_payment_entries_with_party(self, je, amount, party_type, party,
                                                     nachislenie_supplier):
        """Add 4-row entries for nachislenie payment with party"""
        # Row 1: Credit Payable with original Party
        self._add_account_entry(je, self.default_payable_account, credit=amount,
                                party_type=party_type, party=party)
        # Row 2: Debit Cash
        self._add_account_entry(je, self.cash_account, debit=amount)
        # Row 3: Credit Cash
        self._add_account_entry(je, self.cash_account, credit=amount)
        # Row 4: Debit Payable with Nachisleniya supplier
        self._add_account_entry(je, self.default_payable_account, debit=amount,
                                party_type="Supplier", party=nachislenie_supplier)

    def _add_nachislenie_payment_entries_without_party(self, je, amount, nachislenie_supplier):
        """Add 2-row entries for nachislenie payment without party"""
        # Debit Payable with Nachisleniya supplier
        self._add_account_entry(je, self.default_payable_account, debit=amount,
                                party_type="Supplier", party=nachislenie_supplier)
        # Credit Cash
        self._add_account_entry(je, self.cash_account, credit=amount)

    def _add_nachislenie_accrual_entries(self, je, amount, usd_amount, expense_account,
                                          expense_cost_center, nachislenie_supplier):
        """Add 2-row entries for nachislenie accrual"""
        # Credit Payable with Nachisleniya supplier
        self._add_account_entry(je, self.default_payable_account, credit=amount,
                                party_type="Supplier", party=nachislenie_supplier)
        # Debit Expense (USD account)
        self._add_account_entry(je, expense_account, debit=usd_amount,
                                cost_center=expense_cost_center, use_usd_rate=True)
