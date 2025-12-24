# Copyright (c) 2025, Asadbek and contributors
# For license information, please see license.txt

"""
Financial Service

Handles Project creation, Cost Center management, and Employee Advance
for Trip Master.
"""

import frappe
from frappe import _


class FinancialService:
    """Service for financial operations"""

    def __init__(self, trip_master_doc):
        self.trip = trip_master_doc
        self.created_project = None
        self.created_advance = None

    def create_project(self):
        """Create Project for the trip"""
        if not self.trip.company:
            frappe.throw(_("Company is required to create Project"))

        project = frappe.new_doc("Project")
        project.project_name = f"TRIP-MASTER-{self.trip.name}"
        project.company = self.trip.company
        project.project_type = "Internal"
        project.status = "Open"
        project.expected_start_date = self.trip.from_date
        project.expected_end_date = self.trip.to_date

        # Link to Trip Master
        project.custom_trip_master = self.trip.name

        # Set cost center
        project.cost_center = self._get_cost_center()

        # Set budget
        if self.trip.budget_amount:
            project.estimated_costing = self.trip.budget_amount

        project.flags.ignore_permissions = True
        project.insert()

        self.created_project = project.name
        self.trip.db_set("project", project.name)

        frappe.msgprint(
            _("Project {0} created").format(
                frappe.utils.get_link_to_form("Project", project.name)
            )
        )

        return project.name

    def _get_cost_center(self):
        """Get cost center - use provided or company default"""
        if self.trip.cost_center:
            return self.trip.cost_center

        default_cc = frappe.db.get_value(
            "Company", self.trip.company, "cost_center"
        )

        if not default_cc:
            frappe.throw(
                _("No Cost Center specified and Company has no default Cost Center")
            )

        return default_cc

    def create_employee_advance(self, leader):
        """Create Employee Advance for leader"""
        if not self.trip.budget_amount or self.trip.budget_amount <= 0:
            return None

        if not leader:
            frappe.throw(_("Leader is required to create Employee Advance"))

        ea = frappe.new_doc("Employee Advance")
        ea.employee = leader.employee
        ea.posting_date = self.trip.posting_date
        ea.purpose = f"Trip Budget: {self.trip.title}"
        ea.advance_amount = self.trip.budget_amount
        ea.currency = self.trip.currency or "UZS"
        ea.company = self.trip.company
        ea.exchange_rate = 1

        # Link to Trip Master
        ea.custom_trip_master = self.trip.name

        # Link to project
        if self.created_project:
            ea.project = self.created_project

        # Set advance account from Trip Master or company default
        ea.advance_account = self.trip.advance_account or self._get_advance_account()

        # Set payment account if provided
        if self.trip.payment_account:
            ea.mode_of_payment_account = self.trip.payment_account

        ea.flags.ignore_permissions = True
        ea.insert()
        ea.submit()

        leader.employee_advance = ea.name
        self.created_advance = ea.name

        frappe.msgprint(
            _("Employee Advance {0} created for {1}").format(
                frappe.utils.get_link_to_form("Employee Advance", ea.name),
                leader.employee_name
            )
        )

        return ea.name

    def _get_advance_account(self):
        """Get employee advance account from company"""
        advance_account = frappe.db.get_value(
            "Company", self.trip.company, "default_employee_advance_account"
        )

        if not advance_account:
            frappe.throw(
                _("Company {0} does not have default Employee Advance Account").format(
                    self.trip.company
                )
            )

        return advance_account

    def cancel_employee_advance(self, leader):
        """Cancel linked Employee Advance"""
        if not leader or not leader.employee_advance:
            return

        try:
            ea = frappe.get_doc("Employee Advance", leader.employee_advance)
            if ea.docstatus == 1 and ea.status in ["Unpaid", "Paid"]:
                ea.flags.ignore_permissions = True
                ea.cancel()
                frappe.msgprint(
                    _("Employee Advance {0} cancelled").format(ea.name)
                )
        except Exception as e:
            frappe.log_error(f"Error cancelling Employee Advance: {e}")

    def validate_dates(self):
        """Validate trip dates"""
        from frappe.utils import getdate

        if getdate(self.trip.from_date) > getdate(self.trip.to_date):
            frappe.throw(_("From Date cannot be after To Date"))

    def complete_project(self):
        """Mark linked project as completed"""
        if not self.trip.project:
            return

        try:
            project = frappe.get_doc("Project", self.trip.project)
        except frappe.DoesNotExistError:
            return

        if project.status != "Completed":
            project.status = "Completed"
            project.percent_complete_method = "Manual"
            project.percent_complete = 100
            project.flags.ignore_permissions = True
            project.save()
