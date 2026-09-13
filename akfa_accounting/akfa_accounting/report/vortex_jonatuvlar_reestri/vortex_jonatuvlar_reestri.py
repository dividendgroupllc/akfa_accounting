# Copyright (c) 2026, Asadbek and contributors
# For license information, please see license.txt

"""Vortex Jo'natuvlar Reestri — har jo'natilgan tovar qatori alohida satr.
Zavod narxi/summasi/foyda faqat ofis rollariga."""

import frappe
from frappe import _

from akfa_accounting.vortex_narx import ofis_huquqi


def execute(filters=None):
	filters = frappe._dict(filters or {})
	ofis = ofis_huquqi()
	return get_columns(ofis), get_data(filters, ofis)


def get_columns(ofis):
	c = [
		{"fieldname": "posting_date", "label": _("Sana"), "fieldtype": "Date", "width": 95},
		{"fieldname": "jonatuv", "label": _("Jo'natuv"), "fieldtype": "Link", "options": "Vortex Jonatuv", "width": 120},
		{"fieldname": "zayavka", "label": _("Zayavka"), "fieldtype": "Link", "options": "Vortex Zayavka", "width": 120},
		{"fieldname": "manager_name", "label": _("Manager"), "fieldtype": "Data", "width": 120},
		{"fieldname": "customer_name", "label": _("Mijoz"), "fieldtype": "Data", "width": 140},
		{"fieldname": "customer_phone", "label": _("Telefon"), "fieldtype": "Data", "width": 105},
		{"fieldname": "item", "label": _("Tovar"), "fieldtype": "Link", "options": "Item", "width": 130},
		{"fieldname": "uom", "label": _("O'lchov"), "fieldtype": "Data", "width": 80},
		{"fieldname": "qty", "label": _("Miqdor"), "fieldtype": "Float", "precision": 2, "width": 80},
	]
	if ofis:
		c += [{"fieldname": "zavod_narx", "label": _("Zavod narxi"), "fieldtype": "Currency", "options": "currency", "width": 105},
		      {"fieldname": "zavod_summa", "label": _("Zavod summasi"), "fieldtype": "Currency", "options": "currency", "width": 125}]
	c += [{"fieldname": "vortex_narx", "label": _("Narx"), "fieldtype": "Currency", "options": "currency", "width": 105},
	      {"fieldname": "vortex_summa", "label": _("Summa"), "fieldtype": "Currency", "options": "currency", "width": 125}]
	if ofis:
		c += [{"fieldname": "foyda", "label": _("Foyda"), "fieldtype": "Currency", "options": "currency", "width": 110}]
	c += [{"fieldname": "transport", "label": _("Transport"), "fieldtype": "Data", "width": 105},
	      {"fieldname": "mashina_raqami", "label": _("Mashina"), "fieldtype": "Data", "width": 90},
	      {"fieldname": "qabul_holati", "label": _("Manager qabuli"), "fieldtype": "Data", "width": 110},
	      {"fieldname": "currency", "label": _("Valyuta"), "fieldtype": "Link", "options": "Currency", "hidden": 1}]
	return c


def get_data(filters, ofis):
	shart, q = ["j.docstatus = 1"], {}
	for f, op in (("from_date", ">="), ("to_date", "<=")):
		if filters.get(f):
			shart.append(f"j.posting_date {op} %({f})s"); q[f] = filters[f]
	if filters.get("customer"):
		shart.append("j.customer = %(customer)s"); q["customer"] = filters.customer
	if filters.get("qabul_holati"):
		shart.append("j.qabul_holati = %(qabul_holati)s"); q["qabul_holati"] = filters.qabul_holati
	if not ofis:
		shart.append("z.owner = %(own)s"); q["own"] = frappe.session.user

	ofis_ust = "t.zavod_narx, t.zavod_summa, t.foyda," if ofis else ""
	return frappe.db.sql(
		f"""SELECT j.posting_date, j.name AS jonatuv, j.zayavka, mu.full_name AS manager_name,
		           j.customer_name, z.customer_phone, j.transport, j.mashina_raqami, j.qabul_holati, j.currency,
		           t.item, t.uom, t.qty, {ofis_ust} t.vortex_narx, t.vortex_summa
		    FROM `tabVortex Jonatuv` j
		    JOIN `tabVortex Jonatuv Tovar` t ON t.parent = j.name
		    LEFT JOIN `tabVortex Zayavka` z ON z.name = j.zayavka
		    LEFT JOIN `tabUser` mu ON mu.name = z.owner
		    WHERE {' AND '.join(shart)}
		    ORDER BY j.posting_date, j.name, t.idx""",
		q, as_dict=True,
	)
