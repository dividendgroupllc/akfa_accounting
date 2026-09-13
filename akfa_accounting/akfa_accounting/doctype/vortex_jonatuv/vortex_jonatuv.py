# Copyright (c) 2026, Asadbek and contributors
# For license information, please see license.txt

"""Vortex Jo'natuv — zavoddan mijozga jo'natish (qisman yoki to'liq).

Narx bo'linishi: SOTUV narxi (vortex_narx) zayavkada belgilanadi va shu yerga
o'zgarmasdan ko'chadi; ZAVOD narxini jo'natuvchi yozadi va u sotuv narxidan kamida
MIN_MARJA (20 000) past bo'lishi shart — foyda shu farqdan chiqadi.
Jo'natuvchi qo'lda qo'shgan qatorlarda (poddon, salafan va h.k.) ustama yo'q:
sotuv narxi zavod narxiga teng qilib qo'yiladi, ya'ni SI va PI bir xil, foyda 0.
Submit = «jo'natdim»: shu paytda Purchase Invoice (zavod narxi) + Sales Invoice
(vortex narxi) bir vaqtda yaratiladi. Keyin manager «Qabul qildim» deb tasdiqlaydi.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, now_datetime

from akfa_accounting.vortex_narx import (
	COMPANY, CURRENCY, SUPPLIER, MIN_MARJA, ITEM_GROUP, ZAVOD_COST_CENTER,
	ZAVOD_PRICE_LIST, VORTEX_PRICE_LIST,
	uom_factor, default_narx, ofis_huquqi, jami_olcham,
)

QABUL_KUTILMOQDA = "Kutilmoqda"
QABUL_QILINDI = "Qabul qilindi"
EPS = 0.001


class VortexJonatuv(Document):
	def insert(self, *args, **kwargs):
		# Amend: Frappe (UI ham, frappe.copy_doc ham) no_copy maydonlarni ko'chiradi,
		# _validate_links esa validate() dan OLDIN ishlaydi -- bekor qilingan PI/SI
		# havolasi "Cannot link cancelled document" beradi. Shu yerda tozalaymiz.
		if self.amended_from:
			self.purchase_invoice = None
			self.sales_invoice = None
			self.qabul_holati = QABUL_KUTILMOQDA
			self.qabul_qilgan = None
			self.qabul_sana = None
		return super().insert(*args, **kwargs)

	def validate(self):
		self.company = COMPANY
		self.currency = CURRENCY
		self.supplier = self.supplier or SUPPLIER
		self._cost_center_tekshiruvi()
		if not self.tovarlar:
			frappe.throw(_("Kamida bitta tovar qatori kiriting"))
		self._buyurilgan = self._zayavka_qatorlari()
		self.hisobla()
		self._ortiqcha_tekshiruvi()
		self._manzilni_toldir()

	def _cost_center_tekshiruvi(self):
		"""Cost Center POSTAVCHIKDAN avtomatik olinadi -- moslik vortex_setup.py
		dagi ZAVOD_COST_CENTER ro'yxatida. Ro'yxatda bo'lmasa kompaniyaning default
		markazi ishlatiladi. Qo'lda tanlanmaydi, ya'ni zavod va markaz chalkashmaydi.

		Tekshiruv shu yerda turadi, chunki ERPNext noto'g'ri markazni faqat invoice
		submit bo'layotganda aytadi -- bu juda kech."""
		self.cost_center = ZAVOD_COST_CENTER.get(self.supplier) or frappe.get_cached_value(
			"Company", self.company, "cost_center"
		)
		if not self.cost_center:
			frappe.throw(_("{0} kompaniyasida default Cost Center sozlanmagan").format(self.company))

		cc = frappe.get_cached_value(
			"Cost Center", self.cost_center, ["company", "is_group"], as_dict=True
		)
		if not cc:
			frappe.throw(_("Cost Center {0} topilmadi").format(self.cost_center))
		if cc.company != self.company:
			frappe.throw(_("Cost Center {0} — {1} kompaniyasiniki emas").format(self.cost_center, self.company))
		if cc.is_group:
			frappe.throw(_("Cost Center {0} guruh — oxirgi (leaf) markazni tanlang").format(self.cost_center))

	def _zayavka_qatorlari(self):
		"""Zayavkaning qatorlari {qator_nomi: qator}. Bir marta o'qiymiz."""
		zayavka = frappe.get_doc("Vortex Zayavka", self.zayavka)
		if zayavka.docstatus != 1:
			frappe.throw(_("Zayavka {0} hali ofis tomonidan qabul qilinmagan").format(self.zayavka))
		if self.posting_date and zayavka.posting_date and getdate(self.posting_date) < getdate(zayavka.posting_date):
			frappe.throw(_("Jo'natish sanasi ({0}) zayavka sanasidan ({1}) oldin bo'lishi mumkin emas")
			             .format(frappe.format(self.posting_date), frappe.format(zayavka.posting_date)))
		self.customer = zayavka.customer
		self.obyekt = zayavka.obyekt
		return {r.name: r for r in zayavka.tovarlar}

	def _manzilni_toldir(self):
		"""Yuk manzili bo'sh bo'lsa obyekt joylashuvidan olinadi (ustidan yozilmaydi)."""
		if self.obyekt and not (self.yuk_manzili or "").strip():
			self.yuk_manzili = frappe.db.get_value("Customer Site", self.obyekt, "location")

	def hisobla(self):
		"""Sotuv narxi — zayavkadan (o'zgartirib bo'lmaydi). Zavod narxini jo'natuvchi
		yozadi; bo'sh bo'lsa Item Price'dan default. Summa = miqdor × narx (qator o'lchovida)."""
		buyurilgan = getattr(self, "_buyurilgan", None) or self._zayavka_qatorlari()
		v_jami = z_jami = 0.0
		for row in self.tovarlar:
			if not row.uom:
				frappe.throw(_("{0}-qator: o'lchov birligini tanlang").format(row.idx))
			if flt(row.qty) <= 0:
				frappe.throw(_("{0}-qator: miqdor musbat bo'lishi kerak").format(row.idx))
			row.currency = self.currency
			row.conversion_factor = uom_factor(row.item, row.uom)
			row.stock_qty = flt(row.qty) * row.conversion_factor

			zayavka_qator = buyurilgan.get(row.zayavka_qator) if row.zayavka_qator else None
			if zayavka_qator:
				# Sotuv narxi zayavkada belgilangan — shu yerda tahrirlab bo'lmaydi.
				# Jo'natuv boshqa o'lchovda bo'lishi mumkin (zayavka m³ da, jo'natuv
				# poddonda), shuning uchun narx asosiy o'lchov orqali qayta hisoblanadi:
				#   500 000/m³ × 1.68 m³/poddon = 840 000/poddon
				z_factor = flt(zayavka_qator.conversion_factor) or 1
				row.vortex_narx = flt(
					flt(zayavka_qator.vortex_narx) / z_factor * flt(row.conversion_factor),
					row.precision("vortex_narx"),
				)
			if not flt(row.zavod_narx):
				row.zavod_narx = default_narx(row.item, row.uom, ZAVOD_PRICE_LIST)
			if not zayavka_qator:
				# Qo'lda qo'shilgan qator — har qanday tovar bo'lishi mumkin (poddon,
				# salafan, tasma...). Bularda ustama qo'yilmaydi: mijozga zavod
				# narxining o'zida yoziladi, ya'ni SI va PI bir xil, foyda 0.
				# Foyda faqat zayavkadan kelgan tovarlardan chiqadi.
				row.vortex_narx = flt(row.zavod_narx)
			self._narx_tekshiruvi(row, zayavka_qator)
			row.vortex_summa = flt(row.qty) * flt(row.vortex_narx)
			row.zavod_summa = flt(row.qty) * flt(row.zavod_narx)
			row.foyda = row.vortex_summa - row.zavod_summa
			v_jami += row.vortex_summa
			z_jami += row.zavod_summa
		self.vortex_jami = v_jami
		self.zavod_jami = z_jami
		self.foyda_jami = v_jami - z_jami
		self.jami_olcham = jami_olcham(self.tovarlar)

	def _narx_tekshiruvi(self, row, zayavka_qator):
		"""Zayavkadan ko'chirilgan qatorda zavod narxi sotuv narxidan kamida
		MIN_MARJA past bo'lishi shart. Qo'lda qo'shilgan qatorlar (poddon, salafan
		va boshqa qo'shimchalar) zayavkada bo'lmaydi — ularga qoida tegmaydi."""
		if not zayavka_qator:
			return

		sotuv, zavod = flt(row.vortex_narx), flt(row.zavod_narx)
		if sotuv <= 0:
			frappe.throw(_("{0}-qator ({1}): zayavkada sotuv narxi ko'rsatilmagan").format(row.idx, row.item))
		if zavod <= 0:
			frappe.throw(_("{0}-qator ({1}): zavod narxini kiriting").format(row.idx, row.item))

		# MIN_MARJA asosiy o'lchovga (m³) nisbatan belgilangan — qator boshqa
		# o'lchovda bo'lsa talab ham shunga mos ravishda ko'payadi, aks holda
		# poddonda jo'natish orqali marjani ixchamlashtirib yuborish mumkin edi.
		kerakli_marja = MIN_MARJA * (flt(row.conversion_factor) or 1)
		eng_kop = sotuv - kerakli_marja
		if zavod > eng_kop + EPS:
			frappe.throw(_(
				"{0}-qator ({1}): zavod narxi ko'pi bilan {2} bo'lishi mumkin — "
				"sotuv narxi {3}, eng kam farq {4}. Siz {5} kiritdingiz."
			).format(
				row.idx, row.item,
				frappe.format_value(eng_kop, {"fieldtype": "Currency", "options": "currency"}, self),
				frappe.format_value(sotuv, {"fieldtype": "Currency", "options": "currency"}, self),
				frappe.format_value(kerakli_marja, {"fieldtype": "Currency", "options": "currency"}, self),
				frappe.format_value(zavod, {"fieldtype": "Currency", "options": "currency"}, self),
			))

	def _ortiqcha_tekshiruvi(self):
		"""Zayavkada buyurilgan miqdordan (stock uom) ko'p jo'natib bo'lmaydi.

		Qatorlar ikki xil bo'ladi:
		  * zayavka_qator to'ldirilgan — zayavkadan ko'chirilgan, miqdori nazorat ostida;
		  * zayavka_qator bo'sh — jo'natuvchi qo'shgan qo'shimcha (poddon, salafan...).
		Qo'shimcha qator zayavkadagi tovarning o'zi bo'lsa, u nazoratni chetlab o'tib
		ketardi — shuning uchun bunday qator taqiqlanadi.
		"""
		buyurilgan = getattr(self, "_buyurilgan", None) or self._zayavka_qatorlari()

		# Submit paytida zayavka qatorini qulflaymiz: ikki user bir vaqtda submit
		# qilsa, ikkinchisi birinchisining natijasini ko'rib, ortiqchani ushlaydi.
		if self.docstatus == 1:
			frappe.db.sql("SELECT name FROM `tabVortex Zayavka` WHERE name = %s FOR UPDATE", self.zayavka)

		boshqalar = dict(frappe.db.sql(
			"""SELECT t.zayavka_qator, SUM(t.stock_qty)
			   FROM `tabVortex Jonatuv Tovar` t JOIN `tabVortex Jonatuv` j ON j.name = t.parent
			   WHERE j.zayavka = %s AND j.docstatus = 1 AND j.name != %s GROUP BY t.zayavka_qator""",
			(self.zayavka, self.name or ""),
		))
		zayavka_tovarlari = {r.item for r in buyurilgan.values()}
		shu_hujjatda = {}
		bogliq_qator_bor = False

		for row in self.tovarlar:
			if not row.zayavka_qator:
				# Qo'shimcha qator faqat tara/salafan kabi yordamchi tovar bo'lishi mumkin.
				# Gazoblokning o'zi (har qanday o'lcham) faqat zayavka orqali jo'natiladi --
				# aks holda buyurtmadagi miqdor nazoratini boshqa o'lcham bilan chetlab o'tish mumkin.
				if row.item in zayavka_tovarlari:
					frappe.throw(_(
						"{0}-qator ({1}): bu tovar zayavkada bor — qatorni qo'lda qo'shmang, "
						"zayavkadan ko'chirilgan qatordagi miqdorni o'zgartiring"
					).format(row.idx, row.item))
				if frappe.get_cached_value("Item", row.item, "item_group") == ITEM_GROUP:
					frappe.throw(_(
						"{0}-qator ({1}): gazoblok faqat zayavka bo'yicha jo'natiladi — "
						"kerak bo'lsa zayavkaga qator qo'shing"
					).format(row.idx, row.item))
				continue
			bogliq_qator_bor = True

			qator = buyurilgan.get(row.zayavka_qator)
			if not qator:
				# Zayavka almashtirilgan yoki qator o'chirilgan — bog'lanish yaroqsiz.
				frappe.throw(_(
					"{0}-qator: zayavka qatori topilmadi. Jo'natuvni {1} zayavkasidan "
					"qaytadan yarating"
				).format(row.idx, self.zayavka))
			if row.item != qator.item:
				frappe.throw(_(
					"{0}-qator: zayavkada «{1}» buyurilgan, siz «{2}» ni qo'ydingiz — "
					"tovarni almashtirib bo'lmaydi"
				).format(row.idx, qator.item, row.item))

			# Shu hujjatdagi bir xil zayavka qatoriga tegishli qatorlar ham qo'shiladi.
			shu_hujjatda[row.zayavka_qator] = shu_hujjatda.get(row.zayavka_qator, 0.0) + flt(row.stock_qty)
			kerak = flt(qator.stock_qty)
			jami = flt(boshqalar.get(row.zayavka_qator, 0)) + shu_hujjatda[row.zayavka_qator]
			if jami > kerak + EPS:
				frappe.throw(_("{0}: zayavkada {1}, jo'natilmoqchi jami {2} (asosiy o'lchovda) — ortiqcha")
				             .format(qator.item, round(kerak, 3), round(jami, 3)))

		if not bogliq_qator_bor:
			frappe.throw(_("Jo'natuvda zayavkadan kamida bitta tovar qatori bo'lishi kerak"))

	# ------------------------------------------------------------ submit / cancel

	def on_submit(self):
		self.db_set("purchase_invoice", self._invoice("Purchase Invoice", "zavod_narx"))
		self.db_set("sales_invoice", self._invoice("Sales Invoice", "vortex_narx"))
		frappe.get_doc("Vortex Zayavka", self.zayavka).holatni_yangila()

	def on_cancel(self):
		self.flags.ignore_links = True
		for doctype, name in (("Sales Invoice", self.sales_invoice), ("Purchase Invoice", self.purchase_invoice)):
			if name and frappe.db.get_value(doctype, name, "docstatus") == 1:
				d = frappe.get_doc(doctype, name)
				d.flags.ignore_permissions = True
				d.cancel()
		self.db_set({"qabul_holati": QABUL_KUTILMOQDA, "qabul_qilgan": None, "qabul_sana": None})
		frappe.get_doc("Vortex Zayavka", self.zayavka).holatni_yangila()

	def _invoice(self, doctype, narx_maydoni):
		"""Purchase/Sales Invoice yaratadi. Narx tanlangan UOM ga; ombor yangilanmaydi."""
		cost_center = self.cost_center
		items = [{
			"item_code": r.item, "qty": flt(r.qty), "uom": r.uom,
			"conversion_factor": flt(r.conversion_factor) or 1,
			# price_list_rate ham shu narx: aks holda ERPNext ro'yxat narxi bilan farqni
			# "chegirma" deb yozadi va chop etilgan hujjatda 20% chegirma ko'rinib qoladi.
			"rate": flt(r.get(narx_maydoni)), "price_list_rate": flt(r.get(narx_maydoni)),
			"cost_center": cost_center,
		} for r in self.tovarlar]
		umumiy = {
			"doctype": doctype, "company": COMPANY, "posting_date": self.posting_date,
			"set_posting_time": 1, "currency": CURRENCY, "conversion_rate": 1,
			"update_stock": 0, "ignore_pricing_rule": 1, "cost_center": cost_center, "items": items,
			"remarks": f"Vortex Jo'natuv {self.name} (Zayavka {self.zayavka})",
		}
		# Narx ro'yxati ataylab qotiriladi: sukut bo'yicha ERPNext Selling/Buying
		# Settings'dagi "Standard Selling/Buying" (USD) ni oladi va rate=0 qatorni
		# o'sha ro'yxatdan jimgina qayta narxlab yuborishi mumkin.
		if doctype == "Purchase Invoice":
			umumiy["supplier"] = self.supplier
			umumiy["buying_price_list"] = ZAVOD_PRICE_LIST
			umumiy["price_list_currency"] = CURRENCY
			umumiy["plc_conversion_rate"] = 1
		else:
			umumiy["customer"] = self.customer
			umumiy["selling_price_list"] = VORTEX_PRICE_LIST
			umumiy["price_list_currency"] = CURRENCY
			umumiy["plc_conversion_rate"] = 1
		doc = frappe.get_doc(umumiy)
		doc.flags.ignore_permissions = True
		doc.insert()
		doc.submit()
		return doc.name

	# ------------------------------------------------------------ manager qabuli

	@frappe.whitelist()
	def qabul_qildim(self):
		"""Manager molni oldim deb tasdiqlaydi. Faqat shu zayavkaning manageri yoki ofis."""
		if self.docstatus != 1:
			frappe.throw(_("Faqat jo'natilgan hujjatni qabul qilish mumkin"))
		if self.qabul_holati == QABUL_QILINDI:
			frappe.throw(_("Allaqachon qabul qilingan"))
		zayavka_owner = frappe.db.get_value("Vortex Zayavka", self.zayavka, "owner")
		if not ofis_huquqi() and frappe.session.user != zayavka_owner:
			frappe.throw(_("Bu jo'natuvni faqat zayavkani yaratgan manager qabul qila oladi"), frappe.PermissionError)
		self.db_set({"qabul_holati": QABUL_QILINDI, "qabul_qilgan": frappe.session.user, "qabul_sana": now_datetime()})
		return {"qabul_holati": QABUL_QILINDI}
