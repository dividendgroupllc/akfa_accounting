import frappe

# Currency maydonlarining `options` i endi shu yashirin maydonlarga ishora qiladi.
# Frappe `options` ni valyuta kodi emas, MAYDON NOMI deb o'qiydi (meta.py: get_field_currency),
# shuning uchun ilgari "USD"/"UZS" deb yozilgani hech qachon topilmagan va tizim
# kompaniya valyutasiga (USD) tushib, UZS ustunlarini ham $ bilan ko'rsatgan.
FIELDS = {
	"Cash Distribution Entry": {"cur_usd": "USD", "cur_uzs": "UZS"},
	"Cash Distribution Category Summary": {"cur_usd": "USD", "cur_uzs": "UZS"},
	"Cash Distribution Detail": {"cur_usd": "USD"},
	"Cash Distribution Rasxod Item": {"cur_usd": "USD"},
}


def execute():
	"""Yangi yashirin valyuta-kod maydonlarini mavjud yozuvlarga to'ldiradi.

	Maydonlar hujjatlardan keyin qo'shilgani uchun eski qatorlarda ular NULL bo'ladi;
	NULL bo'lsa Frappe yana zaxira valyutaga tushadi va xato qaytadi."""
	for doctype, defaults in FIELDS.items():
		if not frappe.db.table_exists(doctype):
			continue

		for fieldname, value in defaults.items():
			if not frappe.db.has_column(doctype, fieldname):
				continue

			frappe.db.sql(
				"""update `tab{doctype}` set `{fieldname}` = %s
				where `{fieldname}` is null or `{fieldname}` = ''""".format(
					doctype=doctype, fieldname=fieldname
				),
				value,
			)
