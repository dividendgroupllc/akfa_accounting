import frappe
import math

@frappe.whitelist()
def get_recent_payments(mode_of_payment, start=0, limit=50):
    """Berilgan Mode of Payment bo'yicha oxirgi Payment Entry larni qaytaradi."""
    start = int(start)
    limit = int(limit)

    filters = {
        "docstatus": 1,
        "mode_of_payment": mode_of_payment,
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
        ORDER BY posting_date DESC, modified DESC
        LIMIT %s OFFSET %s
    """, (mode_of_payment, limit, start), as_dict=True)

    total_pages = math.ceil(total / limit) if limit else 1

    return {
        "data": data,
        "total": total,
        "page": (start // limit) + 1 if limit else 1,
        "total_pages": total_pages,
        "limit": limit,
    }
