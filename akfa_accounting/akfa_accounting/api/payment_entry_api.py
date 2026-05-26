import frappe
import math

@frappe.whitelist()
def get_recent_payments(mode_of_payment, posting_date=None, start=0, limit=50):
    """Berilgan Mode of Payment va sana bo'yicha oxirgi Payment Entry larni qaytaradi."""
    start = int(start)
    limit = int(limit)
    
    if not posting_date:
        posting_date = frappe.utils.today()

    filters = {
        "docstatus": 1,
        "mode_of_payment": mode_of_payment,
        "posting_date": posting_date
    }

    total = frappe.db.count("Payment Entry", filters=filters)

    data = frappe.db.sql("""
        SELECT
            name,
            posting_date,
            party_type,
            party,
            paid_amount,
            received_amount,
            paid_from_account_currency,
            paid_to_account_currency,
            status
        FROM `tabPayment Entry`
        WHERE docstatus = 1
          AND mode_of_payment = %s
          AND posting_date = %s
        ORDER BY posting_date DESC, modified DESC
        LIMIT %s OFFSET %s
    """, (mode_of_payment, posting_date, limit, start), as_dict=True)

    total_pages = math.ceil(total / limit) if limit else 1

    return {
        "data": data,
        "total": total,
        "page": (start // limit) + 1 if limit else 1,
        "total_pages": total_pages,
        "limit": limit,
    }


@frappe.whitelist()
def get_payment_entry_defaults(payment_type, mode_of_payment, company, posting_date):
	"""Get default values for Payment Entry based on payment_type and mode_of_payment
	
	Returns:
		dict: Default values for accounts, party, and balances
	"""
	if not all([payment_type, mode_of_payment, company, posting_date]):
		return {}
	
	# Import here to use the utility functions
	from akfa_accounting.utils.payment_entry_utils import (
		ACCOUNT_MAPPINGS, 
		OFIS_GL_SUPPLIERS, 
		MODE_OF_PAYMENT,
		get_account_by_company,
		get_account_balance,
		get_currency_from_mode_of_payment
	)
	
	result = {}
	currency = get_currency_from_mode_of_payment(mode_of_payment)
	
	if payment_type == "Receive":
		# Receive logic
		if mode_of_payment == MODE_OF_PAYMENT["CASH_USD"]:
			account = ACCOUNT_MAPPINGS["USD"]["azimov"]
		elif mode_of_payment == MODE_OF_PAYMENT["CASH_UZS"]:
			account = ACCOUNT_MAPPINGS["UZS"]["azimov"]
		else:
			return result
		
		verified_account = get_account_by_company(account, company)
		if verified_account:
			result["paid_to"] = verified_account
			result["paid_to_account_balance"] = get_account_balance(verified_account, posting_date, company)
	
	elif payment_type == "Pay":
		# Pay logic
		if mode_of_payment == MODE_OF_PAYMENT["CASH_USD"]:
			result["party_type"] = "Supplier"
			result["party"] = OFIS_GL_SUPPLIERS["USD"]
			account = ACCOUNT_MAPPINGS["USD"]["azimov"]
			# Default creditors account for USD
			creditors_account_number = "2110"
		elif mode_of_payment == MODE_OF_PAYMENT["CASH_UZS"]:
			result["party_type"] = "Supplier"
			result["party"] = OFIS_GL_SUPPLIERS["UZS"]
			account = ACCOUNT_MAPPINGS["UZS"]["azimov"]
			# Default creditors account for UZS
			creditors_account_number = "2111"
		else:
			return result
		
		verified_account = get_account_by_company(account, company)
		if verified_account:
			result["paid_from"] = verified_account
			result["paid_from_account_balance"] = get_account_balance(verified_account, posting_date, company)

		creditors_account = frappe.db.get_value(
			"Account",
			{"account_number": creditors_account_number, "company": company},
			"name"
		)
		if creditors_account:
			result["paid_to"] = creditors_account
			result["paid_to_account_balance"] = get_account_balance(creditors_account, posting_date, company)
	
	elif payment_type == "Internal Transfer":
		# Internal Transfer logic
		paid_from_account = None
		paid_to_account = None
		
		if mode_of_payment == MODE_OF_PAYMENT["CASH_USD"]:
			paid_from_account = ACCOUNT_MAPPINGS["USD"]["azimov"]
			paid_to_account = ACCOUNT_MAPPINGS["USD"]["hamidulla"]
		elif mode_of_payment == MODE_OF_PAYMENT["CASH_UZS"]:
			paid_from_account = ACCOUNT_MAPPINGS["UZS"]["azimov"]
			paid_to_account = ACCOUNT_MAPPINGS["UZS"]["hamidulla"]
		elif mode_of_payment == MODE_OF_PAYMENT["EXCHANGE_USD_TO_UZS"]:
			paid_from_account = ACCOUNT_MAPPINGS["USD"]["azimov"]
			paid_to_account = ACCOUNT_MAPPINGS["UZS"]["azimov"]
		elif mode_of_payment == MODE_OF_PAYMENT["EXCHANGE_UZS_TO_USD"]:
			paid_from_account = ACCOUNT_MAPPINGS["UZS"]["azimov"]
			paid_to_account = ACCOUNT_MAPPINGS["USD"]["azimov"]
		
		if paid_from_account:
			verified_from = get_account_by_company(paid_from_account, company)
			if verified_from:
				result["paid_from"] = verified_from
				result["paid_from_account_balance"] = get_account_balance(verified_from, posting_date, company)
		
		if paid_to_account:
			verified_to = get_account_by_company(paid_to_account, company)
			if verified_to:
				result["paid_to"] = verified_to
				result["paid_to_account_balance"] = get_account_balance(verified_to, posting_date, company)
	
	return result


@frappe.whitelist()
def get_party_account_for_currency(party_type, party, company, currency):
	"""Return the party's receivable/payable account that matches the requested currency.

	Customer/Supplier may have a default account in one currency (e.g. USD) but invoices
	in another (e.g. UZS). When mode_of_payment forces a target currency, ERPNext picks
	the party's default account silently, which may mismatch. This explicitly resolves
	the right account or returns None so caller can warn the user.
	"""
	if not all([party_type, party, company, currency]):
		return None

	from erpnext.accounts.party import get_party_account

	default_account = get_party_account(party_type, party, company)
	if default_account:
		acc_currency = frappe.db.get_value("Account", default_account, "account_currency")
		if acc_currency == currency:
			return {"account": default_account, "matched": True}

	root_type = "Receivable" if party_type == "Customer" else "Payable"
	candidate = frappe.db.sql("""
		SELECT pa.account
		FROM `tabParty Account` pa
		INNER JOIN `tabAccount` a ON a.name = pa.account
		WHERE pa.parenttype = %s AND pa.parent = %s
		  AND a.company = %s AND a.account_currency = %s
		LIMIT 1
	""", (party_type, party, company, currency), as_dict=True)

	if candidate:
		return {"account": candidate[0].account, "matched": True}

	fallback = frappe.db.sql("""
		SELECT name FROM `tabAccount`
		WHERE company = %s AND account_currency = %s
		  AND root_type = %s AND is_group = 0
		LIMIT 1
	""", (company, currency, root_type), as_dict=True)

	if fallback:
		return {"account": fallback[0].name, "matched": False}

	return None


@frappe.whitelist()
def get_daily_exchange_rates(date=None):
    """
    Returns exchange rates for USD <-> UZS for the given date or the latest available.
    Directly queries Currency Exchange table for reliability.
    """
    if not date:
        date = frappe.utils.today()
    
    try:
        # Get latest USD -> UZS rate on or before the given date
        usd_to_uzs_entry = frappe.db.get_value(
            "Currency Exchange",
            filters={
                "from_currency": "USD",
                "to_currency": "UZS",
                "date": ["<=", date]
            },
            fieldname=["exchange_rate", "date"],
            order_by="date desc",
            as_dict=True
        )
        
        # Get latest UZS -> USD rate on or before the given date
        uzs_to_usd_entry = frappe.db.get_value(
            "Currency Exchange",
            filters={
                "from_currency": "UZS",
                "to_currency": "USD",
                "date": ["<=", date]
            },
            fieldname=["exchange_rate", "date"],
            order_by="date desc",
            as_dict=True
        )
        
        usd_to_uzs = usd_to_uzs_entry.get("exchange_rate") if usd_to_uzs_entry else None
        actual_date = usd_to_uzs_entry.get("date") if usd_to_uzs_entry else date
        uzs_to_usd = uzs_to_usd_entry.get("exchange_rate") if uzs_to_usd_entry else None
        
        return {
            "usd_to_uzs": usd_to_uzs,
            "uzs_to_usd": uzs_to_usd,
            "date": str(actual_date),
            "requested_date": date
        }
    except Exception as e:
        frappe.log_error(f"Error fetching exchange rates: {e}")
        return {}

