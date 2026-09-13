# Copyright (c) 2026, Asadbek and contributors
# For license information, please see license.txt

"""Vortex Zayavka — managerning buyurtmasi: tovar + o'lchov + miqdor + SOTUV NARXI.

Manager saqlaydi (Yangi). Ofis SUBMIT qiladi = «Qabul qilindi». Keyingi holat
Jo'natuvlardan avtomatik: qisman → «Qisman jo'natildi», to'liq → «Completed».
Jo'natilgan miqdor asosiy (stock) o'lchovda hisoblanadi — Zayavka va Jo'natuv turli
o'lchovda bo'lsa ham (m³ va Poddon) taqqoslash to'g'ri chiqadi.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt

from akfa_accounting.vortex_narx import COMPANY, CURRENCY, uom_factor, jami_olcham

HOLAT_YANGI = "Yangi"
HOLAT_QABUL = "Qabul qilindi"
HOLAT_QISMAN = "Qisman jo'natildi"
HOLAT_COMPLETED = "Completed"
HOLAT_BEKOR = "Bekor"
EPS = 0.001


class VortexZayavka(Document):
	def validate(self):
		# Manager alohida maydon emas — hujjatni yaratgan foydalanuvchi (owner) manager hisoblanadi.
		# Kompaniya tahrirlanadi, lekin bo'sh bo'lsa Vortex; valyuta doim UZS.
		self.company = self.company or COMPANY
		self.currency = CURRENCY
		if not self.tovarlar:
			frappe.throw(_("Kamida bitta tovar qatori kiriting"))
		for row in self.tovarlar:
			if not row.uom:
				frappe.throw(_("{0}-qator: o'lchov birligini tanlang").format(row.idx))
			if flt(row.qty) <= 0:
				frappe.throw(_("{0}-qator: miqdor musbat bo'lishi kerak").format(row.idx))
			row.currency = self.currency
			row.conversion_factor = uom_factor(row.item, row.uom)
			row.stock_qty = flt(row.qty) * row.conversion_factor
			row.qolgan = row.stock_qty - flt(row.jonatilgan)
			# Sotuv narxini zayavka beruvchi yozadi; summa shu narxdan, qator o'lchovida.
			row.vortex_summa = flt(row.qty) * flt(row.vortex_narx)
		self.jami_olcham = jami_olcham(self.tovarlar)
		self.vortex_jami = sum(flt(r.vortex_summa) for r in self.tovarlar)
		self._obyekt_tekshiruvi()
		if self.docstatus == 0:
			self.holat = HOLAT_YANGI

	def _obyekt_tekshiruvi(self):
		"""Obyekt tanlangan mijozga tegishli bo'lishi shart."""
		if not self.obyekt:
			return
		egasi = frappe.db.get_value("Customer Site", self.obyekt, "customer")
		if egasi != self.customer:
			frappe.throw(_("«{0}» obyekti {1} mijoziga tegishli emas").format(self.obyekt, self.customer or "—"))

	def before_submit(self):
		# Narxsiz zayavkani qabul qilib bo'lmaydi -- jo'natuvda zavod narxi shunga
		# solishtiriladi, 0 bo'lsa marja qoidasi ma'nosiz bo'lib qoladi.
		for row in self.tovarlar:
			if flt(row.vortex_narx) <= 0:
				frappe.throw(_("{0}-qator ({1}): sotuv narxini kiriting").format(row.idx, row.item))
		self.holat = HOLAT_QABUL

	def on_update_after_submit(self):
		# zakaz_turi allow_on_submit -- o'zgarsa jo'natuvlardagi nusxasi ham yangilansin.
		frappe.db.sql(
			"UPDATE `tabVortex Jonatuv` SET zakaz_turi = %s WHERE zayavka = %s",
			(self.zakaz_turi, self.name),
		)

	def before_cancel(self):
		jonatuvlar = frappe.get_all("Vortex Jonatuv", {"zayavka": self.name, "docstatus": 1}, pluck="name")
		if jonatuvlar:
			frappe.throw(_("Avval jo'natuvlarni bekor qiling: {0}").format(", ".join(jonatuvlar)))

	def on_cancel(self):
		self.db_set("holat", HOLAT_BEKOR)

	# ------------------------------------------------- Jo'natuvdan chaqiriladi

	def holatni_yangila(self):
		"""Submit qilingan Jo'natuvlar bo'yicha jo'natilgan miqdorni (stock uom) va holatni qayta hisoblaydi."""
		jonatilgan = dict(frappe.db.sql(
			"""SELECT t.zayavka_qator, SUM(t.stock_qty)
			   FROM `tabVortex Jonatuv Tovar` t JOIN `tabVortex Jonatuv` j ON j.name = t.parent
			   WHERE j.zayavka = %s AND j.docstatus = 1 GROUP BY t.zayavka_qator""",
			self.name,
		))
		jami = 0.0
		hammasi = True
		for row in self.tovarlar:
			j = flt(jonatilgan.get(row.name, 0))
			row.db_set("jonatilgan", j, update_modified=False)
			row.db_set("qolgan", max(flt(row.stock_qty) - j, 0), update_modified=False)
			jami += j
			if j + EPS < flt(row.stock_qty):
				hammasi = False
		holat = HOLAT_QABUL if jami < EPS else (HOLAT_COMPLETED if hammasi else HOLAT_QISMAN)
		self.db_set("holat", holat, update_modified=False)


# ----------------------------------------------------------------- Jo'natuv yaratish

@frappe.whitelist()
def make_jonatuv(source_name, target_doc=None):
	"""Zayavkadan Jo'natuv: qolgan miqdorni o'sha o'lchovda taklif qiladi."""
	def qator(source, target, source_parent):
		factor = flt(source.conversion_factor) or 1
		qolgan_stock = flt(source.stock_qty) - flt(source.jonatilgan)
		target.qty = round(qolgan_stock / factor, 3)
		target.zayavka_qator = source.name

	qolgan_bor = frappe.db.sql(
		"""SELECT 1 FROM `tabVortex Zayavka Tovar`
		   WHERE parent = %s AND (stock_qty - jonatilgan) > %s LIMIT 1""",
		(source_name, EPS),
	)
	if not qolgan_bor:
		frappe.throw(_("{0}: jo'natilmagan qoldiq yo'q — hammasi jo'natilgan").format(source_name))

	return get_mapped_doc(
		"Vortex Zayavka", source_name,
		{
			"Vortex Zayavka": {
				"doctype": "Vortex Jonatuv",
				"field_map": {"name": "zayavka"},
				"field_no_map": ["naming_series", "posting_date", "holat"],
				"validation": {"docstatus": ["=", 1]},
			},
			"Vortex Zayavka Tovar": {
				"doctype": "Vortex Jonatuv Tovar",
				# vortex_narx ataylab ko'chiriladi: jo'natuvda sotuv narxi zayavkadan keladi,
				# jo'natuvchi faqat zavod narxini yozadi.
				"field_map": {"uom": "uom"},
				"field_no_map": ["qty", "stock_qty", "jonatilgan", "qolgan", "vortex_summa"],
				"postprocess": qator,
				"condition": lambda d: (flt(d.stock_qty) - flt(d.jonatilgan)) > EPS,
			},
		},
		target_doc,
	)
