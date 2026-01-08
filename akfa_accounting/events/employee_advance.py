"""
Employee Advance Events
Auto-create Payment Entry when Employee Advance is submitted (for Trip workflow)
"""
import frappe
from frappe import _
from frappe.utils import flt


def auto_create_payment_entry(doc, method=None):
    """
    ❌ DISABLED: Auto-payment removed for Enterprise Approval Workflow

    New workflow (Enterprise Standard):
    1. Trip Master created with budget
    2. Employee Advance created and linked to Trip (Status: Unpaid)
    3. Finance Manager reviews and approves
    4. Finance Manager clicks "Approve & Pay" button
    5. Payment Entry created → Money to employee (Status: Paid)

    Old behavior (auto-payment) disabled for better financial control.
    """
    # ❌ AUTO-PAYMENT DISABLED
    # This function is kept for backward compatibility but does nothing
    # Payment now requires manual approval via "Approve & Pay" button

    # Only process if linked to a Trip Master
    if not doc.custom_trip_master:
        return

    # Log that advance was created and awaits approval
    frappe.logger().info(f"Employee Advance {doc.name} created for Trip {doc.custom_trip_master}. Awaiting Finance approval.")

    # Do NOT auto-create payment - this is now handled by approval workflow
    return


def create_payment_entry_for_advance(advance):
    """Create and submit Journal Entry for Employee Advance (standard HRMS approach)"""
    from erpnext.accounts.doctype.journal_entry.journal_entry import get_default_bank_cash_account
    import erpnext
    
    company = advance.company
    
    # Get payment account (cash or bank)
    payment_account = get_default_bank_cash_account(company, account_type="Cash", mode_of_payment=advance.mode_of_payment)
    if not payment_account:
        payment_account = get_default_bank_cash_account(company, account_type="Bank")
    
    if not payment_account:
        frappe.throw(_("No payment account configured. Please set default cash/bank account in Company."))
    
    advance_account_currency = frappe.db.get_value("Account", advance.advance_account, "account_currency")
    
    # Create Journal Entry (not Payment Entry) - this is how HRMS does it
    je = frappe.new_doc("Journal Entry")
    je.posting_date = advance.posting_date
    je.voucher_type = "Bank Entry" if payment_account.get("account_type") == "Bank" else "Cash Entry"
    je.company = company
    je.remark = _("Advance payment for Trip: {0}").format(advance.custom_trip_master)
    je.multi_currency = 0
    
    # Debit Employee Advance Account (money going to employee)
    je.append(
        "accounts",
        {
            "account": advance.advance_account,
            "account_currency": advance_account_currency,
            "exchange_rate": flt(advance.exchange_rate) or 1,
            "debit_in_account_currency": flt(advance.advance_amount),
            "reference_type": "Employee Advance",
            "reference_name": advance.name,
            "party_type": "Employee",
            "party": advance.employee,
            "is_advance": "Yes",
            "cost_center": erpnext.get_default_cost_center(company),
        },
    )
    
    # Credit Cash/Bank Account (money going out)
    je.append(
        "accounts",
        {
            "account": payment_account.get("account"),
            "account_currency": payment_account.get("account_currency"),
            "credit_in_account_currency": flt(advance.advance_amount) * flt(advance.exchange_rate or 1),
            "account_type": payment_account.get("account_type"),
            "exchange_rate": 1,
            "cost_center": erpnext.get_default_cost_center(company),
        },
    )
    
    je.flags.ignore_permissions = True
    je.insert()
    je.submit()
    
    return je


def get_payment_account(company, mode_of_payment=None):
    """Get payment account from mode of payment or company defaults"""
    # Try mode of payment first
    if mode_of_payment:
        account = frappe.db.get_value(
            "Mode of Payment Account",
            {"parent": mode_of_payment, "company": company},
            "default_account"
        )
        if account:
            return account
    
    # Fall back to company defaults
    cash_account = frappe.db.get_value("Company", company, "default_cash_account")
    if cash_account:
        return cash_account
    
    bank_account = frappe.db.get_value("Company", company, "default_bank_account")
    return bank_account


def get_default_mode_of_payment():
    """Get first available mode of payment"""
    modes = frappe.get_all("Mode of Payment", filters={"enabled": 1}, limit=1)
    if modes:
        return modes[0].name
    return "Cash"
