"""Let the finance team open an Employee Advance so they can pay it.

HRMS shows the "Create > Payment" button on a submitted Employee Advance, but
only to a user who can create a Payment Entry - that is Accounts Manager /
Accounts User. Those roles have no read permission on Employee Advance out of
the box, so they cannot open the document to reach the button.

Read (and report) only: paying is done through the Payment Entry, the advance
itself stays owned by HR.
"""

import frappe
from frappe.permissions import add_permission, update_permission_property

DOCTYPE = "Employee Advance"
ROLES = ("Accounts Manager", "Accounts User")


def execute():
	if not frappe.db.exists("DocType", DOCTYPE):
		return

	for role in ROLES:
		if not frappe.db.exists("Role", role):
			continue

		# add_permission copies the standard DocPerms into Custom DocPerms first,
		# so the roles already defined on the doctype keep their permissions.
		add_permission(DOCTYPE, role, 0)
		update_permission_property(DOCTYPE, role, 0, "read", 1)
		update_permission_property(DOCTYPE, role, 0, "report", 1)
