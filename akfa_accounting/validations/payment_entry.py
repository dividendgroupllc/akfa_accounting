import frappe
from frappe import _


def validate_payment_type_role_restrictions(doc, method=None):
    """
    TASK 1: Prevent users with 'davron kassa' role from creating 'Pay' payment entries.

    This validation ensures that even if client-side restrictions are bypassed,
    users with 'davron kassa' role cannot save Payment Entries with payment_type = 'Pay'.

    Args:
        doc: Payment Entry document
        method: Event method (not used, but required by Frappe hooks)
    """
    # Check if current user has 'davron kassa' role
    if frappe.db.exists("Has Role", {"parent": frappe.session.user, "role": "davron kassa"}):
        # Check if user is NOT Administrator (Administrators can do anything)
        if not frappe.db.exists("Has Role", {"parent": frappe.session.user, "role": "Administrator"}):
            # Check if payment_type is "Pay"
            if doc.payment_type == "Pay":
                frappe.throw(
                    _("You do not have permission to create Payment Entries with type 'Pay'. "
                      "Please use 'Receive' or 'Internal Transfer' instead."),
                    title=_("Permission Denied")
                )
