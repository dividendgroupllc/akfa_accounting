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
			paid_from_balance = get_account_balance(verified_account, posting_date, company)
			result["paid_from_account_balance"] = paid_from_balance
			# Set the same balance to paid_to_account_balance
			result["paid_to_account_balance"] = paid_from_balance
		
		# Get creditors account for paid_to
		creditors_account = frappe.db.get_value(
			"Account",
			{"account_number": creditors_account_number, "company": company},
			"name"
		)
		if creditors_account:
			result["paid_to"] = creditors_account
	
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

