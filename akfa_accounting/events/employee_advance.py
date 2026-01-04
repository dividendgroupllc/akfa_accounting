"""
Employee Advance Events
Auto-create Payment Entry when Employee Advance is submitted (for Trip workflow)
"""
import frappe
from frappe import _
from frappe.utils import flt


def auto_create_payment_entry(doc, method=None):
    """
    Auto-create Payment Entry when Employee Advance with Trip Master is submitted.
    This implements the workflow:
    1. Trip Master created with budget
    2. Employee Advance created and linked to Trip
    3. Employee Advance Submit → Auto Payment Entry (Pay) → Money to employee
    4. Employee creates Expense Claims → Deducted from advance
    """
    # Only process if linked to a Trip Master
    if not doc.custom_trip_master:
        return
    
    # Check if Payment Entry already exists for this advance
    existing_pe = frappe.db.exists(
        "Payment Entry",
        {
            "party_type": "Employee",
            "party": doc.employee,
            "docstatus": ["!=", 2],  # Not cancelled
            "custom_employee_advance": doc.name
        }
    )
    
    if existing_pe:
        frappe.msgprint(_("Payment Entry {0} already exists for this advance").format(existing_pe))
        return
    
    try:
        payment_entry = create_payment_entry_for_advance(doc)
        if payment_entry:
            frappe.msgprint(
                _("Payment Entry {0} created and submitted automatically").format(
                    frappe.get_desk_link("Payment Entry", payment_entry.name)
                ),
                alert=True,
                indicator="green"
            )
    except Exception as e:
        frappe.log_error(f"Auto Payment Entry Error: {e}", "Employee Advance")
        frappe.msgprint(
            _("Could not auto-create Payment Entry: {0}. Please create manually.").format(str(e)),
            alert=True,
            indicator="orange"
        )


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
