# Copyright (c) 2026, Asadbek and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate, add_days


def execute(filters=None):
    if not filters:
        filters = {}
    
    # Set default dates (last 10 days)
    if not filters.get("from_date"):
        filters["from_date"] = add_days(frappe.utils.today(), -10)
    if not filters.get("to_date"):
        filters["to_date"] = frappe.utils.today()
    
    columns = get_columns(filters)
    data = get_data(filters)
    message = get_summary_html(filters)
    
    # Frappe expects: columns, data, message, chart, report_summary
    return columns, data, message, None, None


def get_columns(filters):
    """Define report columns"""
    return [
        {
            "label": _("Section"),
            "fieldname": "section",
            "fieldtype": "Data",
            "width": 200
        },
        {
            "label": _("Sana"),
            "fieldname": "posting_date",
            "fieldtype": "Date",
            "width": 100
        },
        {
            "label": _("Тип транзакции"),
            "fieldname": "tranzaksiya_turi",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": _("Supplier"),
            "fieldname": "supplier",
            "fieldtype": "Link",
            "options": "Supplier",
            "width": 180
        },
        {
            "label": _("Valyuta"),
            "fieldname": "currency",
            "fieldtype": "Link",
            "options": "Currency",
            "width": 80
        },
        {
            "label": _("Summa"),
            "fieldname": "amount",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 150
        },
        {
            "label": _("PE/CDE Soni"),
            "fieldname": "count",
            "fieldtype": "Int",
            "width": 80
        },
        {
            "label": _("Hujjat"),
            "fieldname": "document",
            "fieldtype": "Dynamic Link",
            "options": "doctype",
            "width": 180
        },
        {
            "label": _("DocType"),
            "fieldname": "doctype",
            "fieldtype": "Data",
            "hidden": 1
        }
    ]


def get_data(filters):
    """Get report data with 3 sections"""
    data = []
    
    # Get company (default first company)
    company = filters.get("company") or frappe.db.get_single_value("Global Defaults", "default_company")
    if not company:
        company = frappe.db.get_value("Company", {}, "name")
    
    # Get Davron kassa accounts (1110 USD, 1111 UZS)
    davron_accounts = get_davron_accounts(company)
    
    # ========== SECTION 1: TARQATILMAGAN (Undistributed) ==========
    data.append({
        "section": _("📋 TARQATILMAGAN YOZUVLAR"),
        "posting_date": None,
        "tranzaksiya_turi": "",
        "supplier": "",
        "currency": "",
        "amount": None,
        "count": None,
        "document": "",
        "doctype": "",
        "indent": 0,
        "bold": 1
    })
    
    undistributed = get_undistributed_entries(filters, davron_accounts, company)
    for row in undistributed:
        data.append(row)
    
    # Add undistributed totals
    undistributed_totals = get_undistributed_totals(filters, davron_accounts, company)
    for row in undistributed_totals:
        data.append(row)
    
    # ========== SECTION 2: TARQATILGAN (Distributed by Supplier) ==========
    data.append({
        "section": _("✅ TARQATILGAN YOZUVLAR (Supplier bo'yicha)"),
        "posting_date": None,
        "tranzaksiya_turi": "",
        "supplier": "",
        "currency": "",
        "amount": None,
        "count": None,
        "document": "",
        "doctype": "",
        "indent": 0,
        "bold": 1
    })
    
    distributed = get_distributed_entries(filters, company)
    for row in distributed:
        data.append(row)
    
    # Add distributed totals
    distributed_totals = get_distributed_totals(filters, company)
    for row in distributed_totals:
        data.append(row)
    
    # ========== SECTION 3: KUNLIK TAFSILOT ==========
    data.append({
        "section": _("📊 KUNLIK TAFSILOT"),
        "posting_date": None,
        "tranzaksiya_turi": "",
        "supplier": "",
        "currency": "",
        "amount": None,
        "count": None,
        "document": "",
        "doctype": "",
        "indent": 0,
        "bold": 1
    })
    
    daily_summary = get_daily_summary(filters, davron_accounts, company)
    for row in daily_summary:
        data.append(row)
    
    return data


def get_davron_accounts(company):
    """Get Davron kassa accounts (1110 USD, 1111 UZS)"""
    accounts = []
    
    usd_account = frappe.db.get_value(
        "Account",
        {"account_number": "1110", "company": company},
        "name"
    )
    uzs_account = frappe.db.get_value(
        "Account",
        {"account_number": "1111", "company": company},
        "name"
    )
    
    if usd_account:
        accounts.append(usd_account)
    if uzs_account:
        accounts.append(uzs_account)
    
    return accounts


def get_undistributed_entries(filters, davron_accounts, company):
    """Get undistributed Payment Entries grouped by date, tranzaksiya_turi, currency"""
    if not davron_accounts:
        return []
    
    currency_filter = ""
    if filters.get("currency"):
        currency_filter = f"AND pe.paid_to_account_currency = '{filters.get('currency')}'"
    
    query = f"""
        SELECT 
            pe.posting_date,
            IFNULL(pe.custom_tranzaksiya_turi, '') as tranzaksiya_turi,
            pe.paid_to_account_currency as currency,
            CASE 
                WHEN pe.paid_to_account_currency = 'UZS' THEN SUM(pe.received_amount)
                ELSE SUM(pe.paid_amount)
            END as amount,
            COUNT(*) as count
        FROM `tabPayment Entry` pe
        WHERE pe.posting_date BETWEEN %(from_date)s AND %(to_date)s
            AND pe.payment_type = 'Receive'
            AND pe.paid_to IN %(davron_accounts)s
            AND pe.company = %(company)s
            AND pe.docstatus = 1
            AND IFNULL(pe.custom_is_distributed, 0) = 0
            {currency_filter}
        GROUP BY pe.posting_date, pe.custom_tranzaksiya_turi, pe.paid_to_account_currency
        ORDER BY pe.posting_date DESC, pe.custom_tranzaksiya_turi
    """
    
    results = frappe.db.sql(query, {
        "from_date": filters.get("from_date"),
        "to_date": filters.get("to_date"),
        "davron_accounts": davron_accounts,
        "company": company
    }, as_dict=True)
    
    data = []
    for row in results:
        data.append({
            "section": "",
            "posting_date": row.posting_date,
            "tranzaksiya_turi": row.tranzaksiya_turi or "",
            "supplier": "",
            "currency": row.currency,
            "amount": row.amount,
            "count": row.count,
            "document": "",
            "doctype": "Payment Entry",
            "indent": 1
        })
    
    return data


def get_undistributed_totals(filters, davron_accounts, company):
    """Get undistributed totals by currency"""
    if not davron_accounts:
        return []
    
    currency_filter = ""
    if filters.get("currency"):
        currency_filter = f"AND pe.paid_to_account_currency = '{filters.get('currency')}'"
    
    query = f"""
        SELECT 
            pe.paid_to_account_currency as currency,
            CASE 
                WHEN pe.paid_to_account_currency = 'UZS' THEN SUM(pe.received_amount)
                ELSE SUM(pe.paid_amount)
            END as amount,
            COUNT(*) as count
        FROM `tabPayment Entry` pe
        WHERE pe.posting_date BETWEEN %(from_date)s AND %(to_date)s
            AND pe.payment_type = 'Receive'
            AND pe.paid_to IN %(davron_accounts)s
            AND pe.company = %(company)s
            AND pe.docstatus = 1
            AND IFNULL(pe.custom_is_distributed, 0) = 0
            {currency_filter}
        GROUP BY pe.paid_to_account_currency
    """
    
    results = frappe.db.sql(query, {
        "from_date": filters.get("from_date"),
        "to_date": filters.get("to_date"),
        "davron_accounts": davron_accounts,
        "company": company
    }, as_dict=True)
    
    data = []
    for row in results:
        data.append({
            "section": _("JAMI TARQATILMAGAN"),
            "posting_date": None,
            "tranzaksiya_turi": "",
            "supplier": "",
            "currency": row.currency,
            "amount": row.amount,
            "count": row.count,
            "document": "",
            "doctype": "",
            "indent": 0,
            "bold": 1
        })
    
    return data


def get_distributed_entries(filters, company):
    """Get distributed entries from Cash Distribution Entry by supplier"""
    currency_filter = ""
    if filters.get("currency"):
        currency_filter = f"AND cdd.currency = '{filters.get('currency')}'"
    
    query = f"""
        SELECT 
            cde.posting_date,
            cdd.supplier,
            cdd.currency,
            SUM(cdd.amount) as amount,
            cde.name as document,
            COUNT(*) as count
        FROM `tabCash Distribution Entry` cde
        INNER JOIN `tabCash Distribution Detail` cdd ON cdd.parent = cde.name
        WHERE cde.posting_date BETWEEN %(from_date)s AND %(to_date)s
            AND cde.company = %(company)s
            AND cde.docstatus = 1
            {currency_filter}
        GROUP BY cde.posting_date, cdd.supplier, cdd.currency, cde.name
        ORDER BY cde.posting_date DESC, cdd.supplier
    """
    
    results = frappe.db.sql(query, {
        "from_date": filters.get("from_date"),
        "to_date": filters.get("to_date"),
        "company": company
    }, as_dict=True)
    
    data = []
    for row in results:
        data.append({
            "section": "",
            "posting_date": row.posting_date,
            "tranzaksiya_turi": "",
            "supplier": row.supplier,
            "currency": row.currency,
            "amount": row.amount,
            "count": row.count,
            "document": row.document,
            "doctype": "Cash Distribution Entry",
            "indent": 1
        })
    
    return data


def get_distributed_totals(filters, company):
    """Get distributed totals by currency"""
    currency_filter = ""
    if filters.get("currency"):
        currency_filter = f"AND cdd.currency = '{filters.get('currency')}'"
    
    query = f"""
        SELECT 
            cdd.currency,
            SUM(cdd.amount) as amount,
            COUNT(DISTINCT cde.name) as count
        FROM `tabCash Distribution Entry` cde
        INNER JOIN `tabCash Distribution Detail` cdd ON cdd.parent = cde.name
        WHERE cde.posting_date BETWEEN %(from_date)s AND %(to_date)s
            AND cde.company = %(company)s
            AND cde.docstatus = 1
            {currency_filter}
        GROUP BY cdd.currency
    """
    
    results = frappe.db.sql(query, {
        "from_date": filters.get("from_date"),
        "to_date": filters.get("to_date"),
        "company": company
    }, as_dict=True)
    
    data = []
    for row in results:
        data.append({
            "section": _("JAMI TARQATILGAN"),
            "posting_date": None,
            "tranzaksiya_turi": "",
            "supplier": "",
            "currency": row.currency,
            "amount": row.amount,
            "count": row.count,
            "document": "",
            "doctype": "",
            "indent": 0,
            "bold": 1
        })
    
    return data


def get_daily_summary(filters, davron_accounts, company):
    """Get daily summary: received, distributed, balance"""
    if not davron_accounts:
        return []
    
    currency_filter_pe = ""
    currency_filter_cde = ""
    if filters.get("currency"):
        currency_filter_pe = f"AND pe.paid_to_account_currency = '{filters.get('currency')}'"
        currency_filter_cde = f"AND cdd.currency = '{filters.get('currency')}'"
    
    # Get all received amounts by date and currency
    received_query = f"""
        SELECT 
            pe.posting_date,
            pe.paid_to_account_currency as currency,
            CASE 
                WHEN pe.paid_to_account_currency = 'UZS' THEN SUM(pe.received_amount)
                ELSE SUM(pe.paid_amount)
            END as amount
        FROM `tabPayment Entry` pe
        WHERE pe.posting_date BETWEEN %(from_date)s AND %(to_date)s
            AND pe.payment_type = 'Receive'
            AND pe.paid_to IN %(davron_accounts)s
            AND pe.company = %(company)s
            AND pe.docstatus = 1
            {currency_filter_pe}
        GROUP BY pe.posting_date, pe.paid_to_account_currency
    """
    
    received = frappe.db.sql(received_query, {
        "from_date": filters.get("from_date"),
        "to_date": filters.get("to_date"),
        "davron_accounts": davron_accounts,
        "company": company
    }, as_dict=True)
    
    # Get all distributed amounts by date and currency
    distributed_query = f"""
        SELECT 
            cde.posting_date,
            cdd.currency,
            SUM(cdd.amount) as amount
        FROM `tabCash Distribution Entry` cde
        INNER JOIN `tabCash Distribution Detail` cdd ON cdd.parent = cde.name
        WHERE cde.posting_date BETWEEN %(from_date)s AND %(to_date)s
            AND cde.company = %(company)s
            AND cde.docstatus = 1
            {currency_filter_cde}
        GROUP BY cde.posting_date, cdd.currency
    """
    
    distributed = frappe.db.sql(distributed_query, {
        "from_date": filters.get("from_date"),
        "to_date": filters.get("to_date"),
        "company": company
    }, as_dict=True)
    
    # Combine data
    daily_data = {}
    
    for row in received:
        key = (str(row.posting_date), row.currency)
        if key not in daily_data:
            daily_data[key] = {"received": 0, "distributed": 0}
        daily_data[key]["received"] = flt(row.amount)
    
    for row in distributed:
        key = (str(row.posting_date), row.currency)
        if key not in daily_data:
            daily_data[key] = {"received": 0, "distributed": 0}
        daily_data[key]["distributed"] = flt(row.amount)
    
    # Format output
    data = []
    for (date, currency), values in sorted(daily_data.items(), reverse=True):
        received_amt = values["received"]
        distributed_amt = values["distributed"]
        balance = received_amt - distributed_amt
        
        # Received row
        data.append({
            "section": _("Prixod"),
            "posting_date": getdate(date),
            "tranzaksiya_turi": "",
            "supplier": "",
            "currency": currency,
            "amount": received_amt,
            "count": None,
            "document": "",
            "doctype": "",
            "indent": 1
        })
        
        # Distributed row
        data.append({
            "section": _("Tarqatilgan"),
            "posting_date": getdate(date),
            "tranzaksiya_turi": "",
            "supplier": "",
            "currency": currency,
            "amount": distributed_amt,
            "count": None,
            "document": "",
            "doctype": "",
            "indent": 1
        })
        
        # Balance row
        data.append({
            "section": _("Qoldiq"),
            "posting_date": getdate(date),
            "tranzaksiya_turi": "",
            "supplier": "",
            "currency": currency,
            "amount": balance,
            "count": None,
            "document": "",
            "doctype": "",
            "indent": 1,
            "bold": 1 if balance != 0 else 0
        })
    
    return data




def get_summary_html(filters):
    """Generate summary HTML table"""
    company = filters.get("company") or frappe.db.get_single_value("Global Defaults", "default_company")
    if not company:
        company = frappe.db.get_value("Company", {}, "name")
    
    davron_accounts = get_davron_accounts(company)
    
    # Default values
    usd_received = 0
    usd_undistributed = 0
    uzs_received = 0
    uzs_undistributed = 0
    
    if davron_accounts:
        # USD totals
        usd_data = frappe.db.sql("""
            SELECT 
                COALESCE(SUM(paid_amount), 0) as received,
                COALESCE(SUM(CASE WHEN IFNULL(custom_is_distributed, 0) = 0 THEN paid_amount ELSE 0 END), 0) as undistributed
            FROM `tabPayment Entry`
            WHERE posting_date BETWEEN %(from_date)s AND %(to_date)s
                AND payment_type = 'Receive'
                AND paid_to IN %(davron_accounts)s
                AND company = %(company)s
                AND docstatus = 1
                AND paid_to_account_currency = 'USD'
        """, {
            "from_date": filters.get("from_date"),
            "to_date": filters.get("to_date"),
            "davron_accounts": davron_accounts,
            "company": company
        }, as_dict=True)
        
        if usd_data:
            usd_received = flt(usd_data[0].received)
            usd_undistributed = flt(usd_data[0].undistributed)
        
        # UZS totals
        uzs_data = frappe.db.sql("""
            SELECT 
                COALESCE(SUM(received_amount), 0) as received,
                COALESCE(SUM(CASE WHEN IFNULL(custom_is_distributed, 0) = 0 THEN received_amount ELSE 0 END), 0) as undistributed
            FROM `tabPayment Entry`
            WHERE posting_date BETWEEN %(from_date)s AND %(to_date)s
                AND payment_type = 'Receive'
                AND paid_to IN %(davron_accounts)s
                AND company = %(company)s
                AND docstatus = 1
                AND paid_to_account_currency = 'UZS'
        """, {
            "from_date": filters.get("from_date"),
            "to_date": filters.get("to_date"),
            "davron_accounts": davron_accounts,
            "company": company
        }, as_dict=True)
        
        if uzs_data:
            uzs_received = flt(uzs_data[0].received)
            uzs_undistributed = flt(uzs_data[0].undistributed)
    
    # Tarqatilgan summalar
    usd_distributed = usd_received - usd_undistributed
    uzs_distributed = uzs_received - uzs_undistributed
    
    # HTML Table
    html = f"""
    <div style="margin-bottom: 20px; padding: 15px; background-color: #f9f9f9; border-radius: 8px;">
        <h4 style="margin: 0 0 15px 0; color: #333; font-weight: 600;">📊 Umumiy Hisobot</h4>
        <table style="width: 100%; border-collapse: collapse; background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
            <thead>
                <tr style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
                    <th style="padding: 12px 15px; text-align: left; border: 1px solid #ddd; color: white; font-weight: 600;"></th>
                    <th style="padding: 12px 15px; text-align: right; border: 1px solid #ddd; color: white; font-weight: 600;">💵 USD</th>
                    <th style="padding: 12px 15px; text-align: right; border: 1px solid #ddd; color: white; font-weight: 600;">🇺🇿 UZS</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td style="padding: 12px 15px; border: 1px solid #ddd; font-weight: 500;">📥 Jami Prixod</td>
                    <td style="padding: 12px 15px; border: 1px solid #ddd; text-align: right; color: #3498db; font-weight: bold;">{usd_received:,.2f}</td>
                    <td style="padding: 12px 15px; border: 1px solid #ddd; text-align: right; color: #3498db; font-weight: bold;">{uzs_received:,.2f}</td>
                </tr>
                <tr style="background-color: #f8fff8;">
                    <td style="padding: 12px 15px; border: 1px solid #ddd; font-weight: 500;">✅ Tarqatilgan</td>
                    <td style="padding: 12px 15px; border: 1px solid #ddd; text-align: right; color: #27ae60; font-weight: bold;">{usd_distributed:,.2f}</td>
                    <td style="padding: 12px 15px; border: 1px solid #ddd; text-align: right; color: #27ae60; font-weight: bold;">{uzs_distributed:,.2f}</td>
                </tr>
                <tr style="background-color: {'#fff8f8' if usd_undistributed > 0 or uzs_undistributed > 0 else '#f8fff8'};">
                    <td style="padding: 12px 15px; border: 1px solid #ddd; font-weight: 600;">⏳ Tarqatilmagan</td>
                    <td style="padding: 12px 15px; border: 1px solid #ddd; text-align: right; color: {'#e74c3c' if usd_undistributed > 0 else '#27ae60'}; font-weight: bold; font-size: 16px;">{usd_undistributed:,.2f}</td>
                    <td style="padding: 12px 15px; border: 1px solid #ddd; text-align: right; color: {'#e74c3c' if uzs_undistributed > 0 else '#27ae60'}; font-weight: bold; font-size: 16px;">{uzs_undistributed:,.2f}</td>
                </tr>
            </tbody>
        </table>
    </div>
    """
    
    return html
