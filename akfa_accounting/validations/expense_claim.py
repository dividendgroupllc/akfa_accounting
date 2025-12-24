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

    # Check if the expense claim employee is different from current user
    # (e.g., HR creating on behalf of employee - should be allowed)
    if doc.employee != user_employee:
        return

    # Validate that employee is a member of the trip
    member_exists = frappe.db.exists(
        "Trip Member",
        {
            "parent": doc.custom_trip_master,
            "parenttype": "Trip Master",
            "employee": doc.employee
        }
    )

    if not member_exists:
        frappe.throw(
            _("You cannot create Expense Claim for Trip Master {0} because you are not a member of this trip").format(
                frappe.bold(doc.custom_trip_master)
            ),
            frappe.PermissionError
        )
