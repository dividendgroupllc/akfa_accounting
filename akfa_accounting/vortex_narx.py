# Copyright (c) 2026, Asadbek and contributors
# For license information, please see license.txt

"""Vortex — o'lchov, narx va ruxsat yordamchilari.

Standart ERPNext yondashuvi: har Item o'z UOM iga ega. Narx Item Price'dan chiqadi
(zavod uchun bir ro'yxat, sotuv uchun boshqasi), lekin ofis qatorda ustidan yozadi.
Bu yer default narxni va o'lchov konversiyasini beradi; yakuniy qiymat hujjatda.
"""

import frappe
from frappe import _
from frappe.utils import flt

from akfa_accounting.vortex_setup import (  # noqa: F401  (re-export: doctype'lar shu yerdan oladi)
	COMPANY, CURRENCY, SUPPLIER, STOCK_UOM, ITEM_GROUP, MIN_MARJA, ZAVOD_COST_CENTER,
	ZAVOD_PRICE_LIST, VORTEX_PRICE_LIST,
)

OFIS_DOCTYPE = "Vortex Jonatuv"   # ofis huquqi shu doctype'ning permlevel-1 o'qishidan aniqlanadi


def ofis_huquqi(user=None):
	"""«Ofis» = Vortex Jonatuv da permlevel 1 (zavod narxi, cost center) ni o'qiy oladigan user.

	Rol nomi kodda yo'q: rollar va huquqlar Role Permission Manager'da beriladi.
	Permlevel-1 o'qish kimda bo'lsa -- hamma zayavkani ko'radi, zavod narxini oladi,
	«Qabul qildim» ni bosa oladi. Qolganlar faqat o'zi yaratgan hujjatlarni ko'radi."""
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	return 1 in frappe.get_meta(OFIS_DOCTYPE).get_permlevel_access("read", user=user)


def session_employee(user=None):
	return frappe.db.get_value("Employee", {"user_id": user or frappe.session.user, "status": "Active"}, "name")


# ---------------------------------------------------------------- o'lchov / narx

def uom_factor(item, uom):
	"""Item ning tanlangan UOM i asosiy (stock) UOM ga nechaga teng.
	Asosiy UOM uchun 1; konversiya jadvalidan izlanadi."""
	stock_uom = frappe.db.get_value("Item", item, "stock_uom")
	if uom == stock_uom:
		return 1.0
	factor = frappe.db.get_value("UOM Conversion Detail", {"parent": item, "uom": uom}, "conversion_factor")
	if flt(factor) <= 0:
		frappe.throw(_("{0} tovarida «{1}» o'lchov birligi kiritilmagan yoki koeffitsienti noto'g'ri — Item ga tekshiring").format(item, uom))
	return flt(factor)


def default_narx(item, uom, price_list):
	"""Item Price'dan tanlangan UOM uchun narx. Aynan UOM narxi bo'lsa — o'sha;
	bo'lmasa asosiy UOM narxi × konversiya. Topilmasa 0 (ofis qo'lda yozadi)."""
	rate = frappe.db.get_value(
		"Item Price", {"item_code": item, "price_list": price_list, "uom": uom}, "price_list_rate"
	)
	if rate is not None:
		return flt(rate)
	stock_uom = frappe.db.get_value("Item", item, "stock_uom")
	base = frappe.db.get_value(
		"Item Price", {"item_code": item, "price_list": price_list, "uom": stock_uom}, "price_list_rate"
	)
	if base is None:
		base = frappe.db.get_value("Item Price", {"item_code": item, "price_list": price_list}, "price_list_rate")
	return flt(base) * uom_factor(item, uom) if base is not None else 0.0


def jami_olcham(tovarlar):
	"""O'lchov birligi bo'yicha guruhlangan jami: masalan «36 Cubic Meter + 11 Poddon»."""
	yigindi = {}
	for row in tovarlar:
		u = row.get("uom") if hasattr(row, "get") else getattr(row, "uom", None)
		q = flt(row.get("qty") if hasattr(row, "get") else getattr(row, "qty", 0))
		if u and q:
			yigindi[u] = yigindi.get(u, 0) + q
	def _son(x):
		return f"{x:.3f}".rstrip("0").rstrip(".")
	return " + ".join(f"{_son(q)} {u}" for u, q in yigindi.items())


@frappe.whitelist()
def qator_defaults(item, uom=None):
	"""Brauzer uchun: tovar tanlanganda UOM, konversiya va default narxlar.
	Zavod narxi faqat ofis rollariga qaytariladi."""
	# Vortex narxlari ochiq endpoint bo'lib qolmasin: Vortex hujjatlariga kirish
	# huquqi bo'lmagan foydalanuvchi sotuv narxlarini birma-bir so'rab ololmaydi.
	if not (frappe.has_permission("Vortex Zayavka", "read") or frappe.has_permission("Vortex Jonatuv", "read")):
		frappe.throw(_("Ruxsat yo'q"), frappe.PermissionError)
	if not uom:
		uom = frappe.db.get_value("Item", item, "sales_uom") or frappe.db.get_value("Item", item, "stock_uom")
	factor = uom_factor(item, uom)
	natija = {
		"uom": uom,
		"conversion_factor": factor,
		"vortex_narx": default_narx(item, uom, VORTEX_PRICE_LIST),
	}
	if ofis_huquqi():
		natija["zavod_narx"] = default_narx(item, uom, ZAVOD_PRICE_LIST)
	return natija


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def item_uom_query(doctype, txt, searchfield, start, page_len, filters):
	"""set_query: faqat shu Item ga tegishli UOM lar (asosiy + konversiyalar)."""
	item = (filters or {}).get("item")
	if not item:
		return []
	return frappe.db.sql(
		"""SELECT uom FROM `tabUOM Conversion Detail`
		   WHERE parent = %(item)s AND uom LIKE %(txt)s ORDER BY idx""",
		{"item": item, "txt": f"%{txt}%"},
	)


# ---- ruxsat: manager (= hujjatni yaratgan user) faqat o'zinikini ko'radi ----
# Alohida "manager" maydoni yo'q — Frappe ning `owner` (yaratgan foydalanuvchi) ishlatiladi.

def zayavka_query(user=None):
	user = user or frappe.session.user
	if ofis_huquqi(user):
		return ""
	return f"`tabVortex Zayavka`.`owner` = {frappe.db.escape(user)}"


def jonatuv_query(user=None):
	"""Manager o'z zayavkalariga tegishli jo'natuvlarni ko'radi (jo'natuvni ofis yaratadi,
	shuning uchun owner emas — zayavkaning owner'i bo'yicha)."""
	user = user or frappe.session.user
	if ofis_huquqi(user):
		return ""
	return (f"`tabVortex Jonatuv`.`zayavka` IN "
	        f"(SELECT name FROM `tabVortex Zayavka` WHERE owner = {frappe.db.escape(user)})")


def zayavka_permission(doc, ptype=None, user=None):
	user = user or frappe.session.user
	return ofis_huquqi(user) or doc.owner == user


def jonatuv_permission(doc, ptype=None, user=None):
	user = user or frappe.session.user
	if ofis_huquqi(user):
		return True
	return frappe.db.get_value("Vortex Zayavka", doc.zayavka, "owner") == user
