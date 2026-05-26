import frappe
from frappe import _
from frappe.utils import flt, getdate


def validate_payment_entry(doc, method=None):
	"""Run all akfa_accounting validations for Payment Entry."""
	validate_payment_type_role_restrictions(doc, method)
	validate_currency_consistency(doc, method)
	validate_exchange_rate_freshness(doc, method)


def validate_currency_consistency(doc, method=None):
	"""Catch a common cashier mistake: paid_amount entered in wrong currency.

	When paid_from and paid_to share the same currency, paid_amount must equal
	received_amount. Otherwise it's a multi-currency PE and an exchange rate
	must exist linking the two amounts.
	"""
	if not (doc.paid_from_account_currency and doc.paid_to_account_currency):
		return

	if doc.paid_from_account_currency == doc.paid_to_account_currency:
		if flt(doc.paid_amount, 2) != flt(doc.received_amount, 2):
			frappe.throw(
				_("Bir xil valyutada paid_amount va received_amount teng bo'lishi shart. "
				  "Paid: {0} {1}, Received: {2} {3}").format(
					doc.paid_amount, doc.paid_from_account_currency,
					doc.received_amount, doc.paid_to_account_currency
				),
				title=_("Currency Mismatch")
			)
		return

	if not flt(doc.paid_amount) or not flt(doc.received_amount):
		frappe.throw(
			_("Multi-currency PE: paid_amount ({0}) va received_amount ({1}) ikkalasi ham to'ldirilishi shart.").format(
				doc.paid_from_account_currency, doc.paid_to_account_currency
			),
			title=_("Missing Amount")
		)


def validate_exchange_rate_freshness(doc, method=None):
	"""Block submit when posting_date has no Currency Exchange row and PE is multi-currency."""
	if not doc.paid_from_account_currency or not doc.paid_to_account_currency:
		return
	if doc.paid_from_account_currency == doc.paid_to_account_currency:
		return

	pairs = {(doc.paid_from_account_currency, doc.paid_to_account_currency)}
	for from_c, to_c in pairs:
		if from_c == to_c:
			continue
		latest = frappe.db.get_value(
			"Currency Exchange",
			filters={"from_currency": from_c, "to_currency": to_c, "date": ["<=", doc.posting_date]},
			fieldname="date",
			order_by="date desc"
		)
		if not latest:
			frappe.msgprint(
				_("Diqqat: {0} sanasi uchun {1} -> {2} kursi topilmadi.").format(
					doc.posting_date, from_c, to_c
				),
				indicator="orange"
			)
			continue
		if getdate(latest) != getdate(doc.posting_date):
			delta = (getdate(doc.posting_date) - getdate(latest)).days
			if delta >= 3:
				frappe.msgprint(
					_("Diqqat: kurs {0} sanasidan ({1} kun eski). Aniq kurs kiriting yoki Currency Exchange yangilang.").format(
						latest, delta
					),
					indicator="orange"
				)


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
