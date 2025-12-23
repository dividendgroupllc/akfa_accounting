# Copyright (c) 2025, Asadbek and contributors
# For license information, please see license.txt

"""
Journal Entry Creator for Kassa Rasxod

This module provides the main orchestrator for Journal Entry creation.
Delegates to specialized processors for each transaction type.

Transaction Types:
- Rasxod: Expense entries (tz-1 through tz-8)
- Podochot: Employee advance prixod/rasxod
- Koplashga: Transfer between parties via cash
"""

import frappe
from frappe import _

from akfa_accounting.akfa_accounting.doctype.kassa_rasxod.services.rasxod_processor import (
    RasxodProcessor,
)
from akfa_accounting.akfa_accounting.doctype.kassa_rasxod.services.podochot_processor import (
    PodochotProcessor,
)
from akfa_accounting.akfa_accounting.doctype.kassa_rasxod.services.koplashga_processor import (
    KoplashgaProcessor,
)


class JournalEntryCreator:
    """
    Main orchestrator for Journal Entry creation.

    Delegates to specialized processors based on transaction type:
    - RasxodProcessor: Handles expense entries
    - PodochotProcessor: Handles employee advance entries
    - KoplashgaProcessor: Handles transfer entries
    """

    def __init__(self, kassa_rasxod_doc):
        self.doc = kassa_rasxod_doc
        self._rasxod_processor = None
        self._podochot_processor = None
        self._koplashga_processor = None

    @property
    def rasxod_processor(self):
        """Lazy initialization of RasxodProcessor"""
        if self._rasxod_processor is None:
            self._rasxod_processor = RasxodProcessor(self.doc)
        return self._rasxod_processor

    @property
    def podochot_processor(self):
        """Lazy initialization of PodochotProcessor"""
        if self._podochot_processor is None:
            self._podochot_processor = PodochotProcessor(self.doc)
        return self._podochot_processor

    @property
    def koplashga_processor(self):
        """Lazy initialization of KoplashgaProcessor"""
        if self._koplashga_processor is None:
            self._koplashga_processor = KoplashgaProcessor(self.doc)
        return self._koplashga_processor

    def process_rasxod_item(self, item, idx):
        """Process Rasxod (expense) item"""
        return self.rasxod_processor.process_rasxod_item(item, idx)

    def process_podochot_prixod_item(self, item, idx):
        """Process Podochot prixod (employee returns money) item"""
        return self.podochot_processor.process_podochot_prixod_item(item, idx)

    def process_podochot_rasxod_item(self, item, idx):
        """Process Podochot rasxod (employee receives money) item"""
        return self.podochot_processor.process_podochot_rasxod_item(item, idx)

    def process_koplashga_item(self, item, idx):
        """Process Koplashga (transfer) item"""
        return self.koplashga_processor.process_koplashga_item(item, idx)


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
