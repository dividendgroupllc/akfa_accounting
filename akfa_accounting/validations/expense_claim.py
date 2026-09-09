# Copyright (c) 2025, Asadbek and contributors
# For license information, please see license.txt

"""
Expense Claim Validations

Security validations for Trip Master integration
"""

import frappe
from frappe import _


def validate_trip_membership(doc, method=None):
    """
    Validate that employee creating Expense Claim is a member of the Trip Master

    Security Rule: Employees can only create expenses for trips they are part of
    """
    # Skip validation for admins and HR roles
    if "System Manager" in frappe.get_roles() or "HR Manager" in frappe.get_roles():
        return

    # Only validate if custom_trip_master is set
    if not doc.custom_trip_master:
        return

    # Get current user's employee
    current_user = frappe.session.user
    user_employee = frappe.db.get_value("Employee", {"user_id": current_user}, "name")

    if not user_employee:
        return  # No employee linked, let standard permissions handle it

    # Both the acting user and the claim's employee must be on the trip, so that
    # naming somebody else in `employee` cannot be used to bypass the guard.
    for employee in dict.fromkeys([user_employee, doc.employee]):
        if not _is_trip_member(doc.custom_trip_master, employee):
            frappe.throw(
                _("You cannot create Expense Claim for Trip Master {0} because {1} is not a member of this trip").format(
                    frappe.bold(doc.custom_trip_master), frappe.bold(employee)
                ),
                frappe.PermissionError
            )


def _is_trip_member(trip_master, employee):
    return bool(
        frappe.db.exists(
            "Trip Member",
            {
                "parent": trip_master,
                "parenttype": "Trip Master",
                "employee": employee
            }
        )
    )
