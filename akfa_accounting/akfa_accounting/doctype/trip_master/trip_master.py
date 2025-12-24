# Copyright (c) 2025, Asadbek and contributors
# For license information, please see license.txt

"""
Trip Master Controller

Thin controller that delegates business logic to services.
"""

import frappe
from frappe.model.document import Document

from akfa_accounting.akfa_accounting.doctype.trip_master.services.trip_orchestrator import (
    TripOrchestrator,
)


class TripMaster(Document):
    def validate(self):
        self._set_title()
        self._validate_vehicle_availability()

    def before_cancel(self):
        # Skip linked-doc checks; orchestrator cancels dependents
        self.flags.ignore_links = True

    def on_submit(self):
        orchestrator = TripOrchestrator(self)
        orchestrator.on_submit()

    def on_cancel(self):
        self.flags.ignore_links = True
        orchestrator = TripOrchestrator(self)
        orchestrator.on_cancel()

    def _set_title(self):
        """Auto-set title if not provided"""
        if not self.title:
            group_name = self.employee_group or "Trip"
            self.title = f"{group_name} - {self.from_date}"

    def _validate_vehicle_availability(self):
        """Validate all vehicles are available before save"""
        for vehicle_row in self.vehicles:
            status = frappe.db.get_value(
                "Vehicle", vehicle_row.vehicle, "custom_trip_status"
            )

            # Allow if status is None or 'Available'
            if status and status != "Available":
                # Check if it's the same trip (during update)
                current_trip = frappe.db.get_value(
                    "Vehicle", vehicle_row.vehicle, "custom_current_trip"
                )
                if current_trip != self.name:
                    frappe.throw(
                        frappe._("Vehicle {0} is not available. Current status: {1}").format(
                            vehicle_row.vehicle, status
                        )
                    )

    @frappe.whitelist()
    def complete_trip(self):
        orchestrator = TripOrchestrator(self)
        orchestrator.mark_completed()
        return {"status": "Completed"}


def get_permission_query_conditions(user):
    """
    Permission Query: Employees can only see trips they are part of
    """
    if not user:
        user = frappe.session.user

    # Administrator bypass - full access
    if user == "Administrator":
        return ""

    # Admins and HR roles see everything
    if "System Manager" in frappe.get_roles(user) or "HR Manager" in frappe.get_roles(user):
        return ""

    # Get employee linked to user
    employee = frappe.db.get_value("Employee", {"user_id": user}, "name")

    if not employee:
        # User has no employee record, can't see any trips
        return "1=0"

    # Return condition: Trip Master where this employee is a member
    return f"""(`tabTrip Master`.`name` IN (
        SELECT DISTINCT parent
        FROM `tabTrip Member`
        WHERE employee = '{employee}' AND parenttype = 'Trip Master'
    ))"""


def has_permission(doc, user):
    """
    Document-level permission check
    """
    if not user:
        user = frappe.session.user

    # Administrator bypass - full access
    if user == "Administrator":
        return True

    # Admins and HR roles have full access
    if "System Manager" in frappe.get_roles(user) or "HR Manager" in frappe.get_roles(user):
        return True

    # Get employee linked to user
    employee = frappe.db.get_value("Employee", {"user_id": user}, "name")

    if not employee:
        return False

    # Check if employee is a member of this trip
    member_exists = frappe.db.exists(
        "Trip Member",
        {"parent": doc.name, "parenttype": "Trip Master", "employee": employee}
    )

    return bool(member_exists)


@frappe.whitelist()
def get_employees_from_group(employee_group):
    """
    Get all employees from an Employee Group

    Args:
        employee_group: Employee Group name

    Returns:
        list: List of employee dictionaries with name and employee_name
    """
    if not employee_group:
        return []

    # Query Employee Group Table child table
    employees = frappe.get_all(
        "Employee Group Table",
        filters={
            "parent": employee_group,
            "parenttype": "Employee Group"
        },
        fields=["employee", "employee_name"]
    )

    return employees
