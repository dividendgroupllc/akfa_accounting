# Copyright (c) 2025, Asadbek and contributors
# For license information, please see license.txt

"""
Trip Orchestrator Service (Refactored)

Thin orchestrator that delegates to specialized services with transaction handling.
"""

import frappe
from frappe import _

from akfa_accounting.services.provisioning_service import (
    ProvisioningService,
)
from akfa_accounting.services.fleet_service import FleetService
from akfa_accounting.services.financial_service import FinancialService


class TripOrchestrator:
    """
    Orchestrates Trip Master operations with atomic transactions.

    Delegates to:
    - ProvisioningService: Travel Request creation
    - FleetService: Vehicle status management
    - FinancialService: Project & Employee Advance
    """

    def __init__(self, trip_master_doc):
        self.doc = trip_master_doc
        self.provisioning = ProvisioningService(trip_master_doc)
        self.fleet = FleetService(trip_master_doc)
        self.financial = FinancialService(trip_master_doc)

    def on_submit(self):
        """Execute submit workflow"""
        try:
            # Step 1: Validate
            self._validate_all()

            # Step 2: Create Project & get Cost Center
            project_name = self.financial.create_project()

            # Step 3: Create Travel Requests (linked to Project)
            self.provisioning.create_travel_requests(project_name)

            # Step 4: Create Employee Advance for Leader
            leader = self.provisioning.get_leader()
            if leader:
                self.financial.create_employee_advance(leader)

            # Step 5: Allocate Vehicles
            self.fleet.allocate_vehicles()

            # Step 6: Update status
            self.doc.db_set("status", "Active")

        except Exception as e:
            frappe.throw(
                _("Trip Master submit failed: {0}").format(str(e))
            )

    def on_cancel(self):
        """Execute cancel workflow"""
        try:
            # Step 1: Cancel Travel Requests
            self.provisioning.cancel_travel_requests()

            # Step 2: Cancel Employee Advance
            leader = self.provisioning.get_leader()
            if leader:
                self.financial.cancel_employee_advance(leader)

            # Step 3: Release Vehicles
            self.fleet.release_vehicles()

            # Step 4: Update status
            self.doc.db_set("status", "Cancelled")

        except Exception as e:
            frappe.throw(
                _("Trip Master cancel failed: {0}").format(str(e))
            )

    def mark_completed(self):
        """Finish trip, release resources, and close project"""
        try:
            self._close_travel_requests()
            self.fleet.release_vehicles()
            self.financial.complete_project()
            self.doc.db_set("status", "Completed")
        except Exception as e:
            frappe.throw(_("Trip Master completion failed: {0}").format(str(e)))

    def _validate_all(self):
        """Run all validations before submit"""
        self.provisioning.validate_members()
        self.fleet.validate_availability()
        self.financial.validate_dates()

    def _close_travel_requests(self):
        """Mark linked Travel Requests as completed if possible"""
        meta = frappe.get_meta("Travel Request")
        has_status = meta.has_field("status")

        for member in self.doc.members:
            if not member.travel_request:
                continue

            try:
                tr = frappe.get_doc("Travel Request", member.travel_request)
                if tr.docstatus != 1:
                    continue

                if has_status:
                    tr.db_set("status", "Completed")
            except Exception as err:
                frappe.log_error(f"Error completing Travel Request {member.travel_request}: {err}")
