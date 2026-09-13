# Copyright (c) 2026, Asadbek and contributors
# For license information, please see license.txt

"""Vortex — gazoblok savdosi uchun boshlang'ich sozlash.

Hech qanday sozlama doctypesi yo'q: narx qoidalari ERPNext ning o'z narx
ro'yxatlarida yashaydi, kompaniya va zavod — kod konstantalari.
Hammasi idempotent. Ishga tushirish:
  bench --site <sayt> execute akfa_accounting.vortex_setup.setup_vortex
"""

import frappe

COMPANY = "Vortex"
CURRENCY = "UZS"
SUPPLIER = "Zavod gazoblok"
ITEM_GROUP = "Gazoblok"
XIZMAT_GROUP = "Services"
STOCK_UOM = "Cubic Meter"
PALLET_UOM = "Poddon"
ZAVOD_PRICE_LIST = "Zavod narxi"     # xarid — zavod bizga necha puldan beradi
VORTEX_PRICE_LIST = "Vortex narxi"   # sotuv — biz mijozga necha puldan beramiz

# o'lcham -> (bir poddondagi m3, zavod narxi, vortex narxi)  — so'm / m3
# Narx qoidasi: summa = m3 x ro'yxat narxi, boshqa hech narsa. Transport narxga ta'sir qilmaydi.
# Poddon hajmi haqiqiy fizik konfiguratsiyadan: 600x250x300 = 0.045 m3 x 40 dona = 1.8 m3
ITEMS = {
	"600x250x100": {"m3_per_pallet": 1.80, "blocks": 120, "zavod": 620000, "vortex": 640000},
	"600x250x200": {"m3_per_pallet": 1.68, "blocks": 56, "zavod": 620000, "vortex": 640000},
	"600x250x300": {"m3_per_pallet": 1.80, "blocks": 40, "zavod": 620000, "vortex": 640000},
	"600x250x400": {"m3_per_pallet": 1.44, "blocks": 24, "zavod": 620000, "vortex": 640000},
}
ESKI_YETKAZISH_ITEM = "Yetkazib berish"   # avvalgi urinishdan — tozalanadi

# Yog'och poddon — alohida pullik tovar, donada. Narxini ofis ikkala ro'yxatda belgilaydi.
PODDON_ITEM = "Poddon"
PODDON_UOM = "Dona"
PODDON_GROUP = "Tara"
PODDON_NARX = {"zavod": 0, "vortex": 0}   # boshlang'ich — OFIS to'ldirishi shart

ROLES = ["Vortex Manager", "Vortex Ofis"]

# Qaysi zavoddan (postavchik) olingan bo'lsa, PI/SI shu cost center'ga yoziladi.
# Ro'yxatda yo'q postavchik uchun kompaniyaning default markazi ishlatiladi.
# Yangi zavod qo'shilganda shu yerga bitta qator qo'shiladi -- boshqa hech nima.
ZAVOD_COST_CENTER = {
	"Yutong gazoblok": "yutong gazoblok - V",
}

# Eng kam marja (so'm, qatorning o'z o'lchov birligida). Zayavkadan ko'chirilgan
# qatorda zavod narxi sotuv narxidan kamida shuncha past bo'lishi shart:
#     zavod_narx <= vortex_narx - MIN_MARJA
# Jo'natuvchi qo'lda qo'shgan qatorlarga (poddon, salafan, boshqa qo'shimchalar)
# bu qoida TEGMAYDI -- ular zayavkada umuman bo'lmaydi, taqqoslaydigan narx yo'q.
MIN_MARJA = 20000


def setup_vortex():
	fix_company_currency()
	ensure_company_accounts()
	create_uom()
	create_item_groups()
	create_items()
	create_poddon_item()
	create_price_lists()
	create_roles()
	teardown_v1()
	frappe.db.commit()
	print("Vortex sozlandi.")


# ------------------------------------------------------------------ valyuta

def fix_company_currency():
	"""Kompaniya va barcha schotlarini so'mga o'tkazadi (faqat tranzaksiya bo'lmasa).
	AVVAL schotlar, keyin Company — ERPNext default schotlar valyutasini tekshiradi."""
	company = frappe.get_doc("Company", COMPANY)
	if company.default_currency == CURRENCY:
		print(f"  valyuta: allaqachon {CURRENCY}")
		return
	if frappe.db.exists("GL Entry", {"company": COMPANY}):
		frappe.throw(f"{COMPANY} da tranzaksiyalar bor — valyutani o'zgartirib bo'lmaydi")
	eski = company.default_currency
	frappe.db.sql("UPDATE `tabAccount` SET account_currency = %s WHERE company = %s", (CURRENCY, COMPANY))
	frappe.clear_cache()
	company.reload()
	company.default_currency = CURRENCY
	company.save()
	print(f"  valyuta: {eski} -> {CURRENCY}")


# ------------------------------------------------------------- spravochnik

def create_uom():
	for uom in (PALLET_UOM, PODDON_UOM):
		if not frappe.db.exists("UOM", uom):
			frappe.get_doc({"doctype": "UOM", "uom_name": uom, "enabled": 1}).insert()
			print(f"  UOM: {uom}")
	if not frappe.db.get_value("UOM", STOCK_UOM, "enabled"):
		frappe.db.set_value("UOM", STOCK_UOM, "enabled", 1)


def create_item_groups():
	for g in (ITEM_GROUP, PODDON_GROUP):
		if not frappe.db.exists("Item Group", g):
			frappe.get_doc({"doctype": "Item Group", "item_group_name": g,
			                "parent_item_group": "All Item Groups", "is_group": 0}).insert()
			print(f"  Item Group: {g}")


def ensure_company_accounts():
	"""PI/SI qatorlari uchun kompaniyada xarajat va daromad schoti bo'lishi shart."""
	c = frappe.get_doc("Company", COMPANY)
	changed = False
	if not c.default_expense_account:
		cogs = frappe.db.get_value("Account", {"company": COMPANY, "account_name": "Cost of Goods Sold", "is_group": 0}, "name")
		if cogs:
			c.default_expense_account = cogs; changed = True
	if not c.default_income_account:
		sales = frappe.db.get_value("Account", {"company": COMPANY, "account_name": "Sales", "is_group": 0}, "name")
		if sales:
			c.default_income_account = sales; changed = True
	if changed:
		c.save(); print(f"  kompaniya schotlari: xarajat={c.default_expense_account}, daromad={c.default_income_account}")


def _item_defaults():
	"""Vortex uchun daromad/xarajat schotlari — kompaniya standartlaridan."""
	c = frappe.get_cached_doc("Company", COMPANY)
	# Ombor tovari emas, lekin ERPNext qatordagi ombor kompaniyaga tegishli
	# ekanini tekshiradi — bo'sh qoldirilsa boshqa kompaniyanikini yozib yuborishi mumkin.
	ombor = frappe.db.get_value("Warehouse", {"company": COMPANY, "is_group": 0}, "name")
	return {
		"company": COMPANY,
		"default_warehouse": ombor,
		"income_account": c.default_income_account,
		"expense_account": c.default_expense_account or c.stock_adjustment_account,
	}


def _ensure_item_defaults(item_code):
	"""Avval yaratilgan tovarda Vortex kompaniyasi uchun standart schotlar bo'lmasa qo'shadi."""
	if frappe.db.exists("Item Default", {"parent": item_code, "company": COMPANY}):
		return
	item = frappe.get_doc("Item", item_code)
	item.append("item_defaults", _item_defaults())
	item.save()


def create_items():
	"""Har o'lcham — alohida tovar, ombor tovari EMAS (Vortex tovarni ushlamaydi).
	Poddon <-> m3 ERPNext ning o'z UOM konversiyasi orqali."""
	for code, d in ITEMS.items():
		if frappe.db.exists("Item", code):
			_ensure_item_defaults(code)
			continue
		frappe.get_doc({
			"doctype": "Item", "item_code": code,
			"item_name": f"Gazoblok {code.replace('x', '×')}",
			"item_group": ITEM_GROUP, "stock_uom": STOCK_UOM, "is_stock_item": 0,
			"description": f"Gazoblok {code.replace('x', '×')} mm — poddonda {d['blocks']} dona = {d['m3_per_pallet']} m³",
			"uoms": [{"uom": STOCK_UOM, "conversion_factor": 1},
			         {"uom": PALLET_UOM, "conversion_factor": d["m3_per_pallet"]}],
			"item_defaults": [_item_defaults()],
		}).insert()
		print(f"  Item: {code} ({d['m3_per_pallet']} m³/poddon)")



def create_poddon_item():
	"""Yog'och poddon — pullik tovar, donada, ombor tovari emas."""
	if frappe.db.exists("Item", PODDON_ITEM):
		_ensure_item_defaults(PODDON_ITEM)
		return
	frappe.get_doc({
		"doctype": "Item", "item_code": PODDON_ITEM, "item_name": "Yog'och poddon",
		"item_group": PODDON_GROUP, "stock_uom": PODDON_UOM, "is_stock_item": 0,
		"description": "Gazoblok tashiladigan yog'och poddon — alohida pullik, donada",
		"item_defaults": [_item_defaults()],
	}).insert()
	print(f"  Item: {PODDON_ITEM} (dona)")


def create_price_lists():
	"""Ikkita ro'yxat: xarid (Zavod) va sotuv (Vortex). Marja alohida yozilmaydi —
	u shunchaki ikkisining farqi. Yetkazish ham shu ro'yxatlarda, xizmat tovari sifatida."""
	for name, buying, selling in ((ZAVOD_PRICE_LIST, 1, 0), (VORTEX_PRICE_LIST, 0, 1)):
		if not frappe.db.exists("Price List", name):
			frappe.get_doc({"doctype": "Price List", "price_list_name": name, "currency": CURRENCY,
			                "buying": buying, "selling": selling, "enabled": 1}).insert()
			print(f"  Price List: {name}")

	def _price(item, price_list, rate):
		"""Faqat YO'Q bo'lsa yaratadi. Ofis Item Price'ni tahrirlagan bo'lsa -- tegmaydi,
		aks holda setup'ni qayta ishga tushirish narxlarni jimgina konstantaga qaytarib,
		keyingi hamma jo'natuvni noto'g'ri summada chiqarardi."""
		mavjud = frappe.db.get_value(
			"Item Price",
			{"item_code": item, "price_list": price_list, "uom": STOCK_UOM},
			["name", "price_list_rate"],
			as_dict=True,
		)
		if mavjud:
			if float(mavjud.price_list_rate) != float(rate):
				print(f"  narx tegilmadi (ofis belgilagan): {item} / {price_list}: {mavjud.price_list_rate:,.0f}")
			return 0
		frappe.get_doc({"doctype": "Item Price", "item_code": item, "price_list": price_list,
		                "uom": STOCK_UOM, "currency": CURRENCY, "price_list_rate": rate}).insert()
		return 1

	n = 0
	for code, d in ITEMS.items():
		n += _price(code, ZAVOD_PRICE_LIST, d["zavod"]) + _price(code, VORTEX_PRICE_LIST, d["vortex"])
	# Poddon narxi: faqat yo'q bo'lsa 0 bilan yaratiladi — ofis kiritgan narx ustidan yozilmaydi
	for pl, key in ((ZAVOD_PRICE_LIST, "zavod"), (VORTEX_PRICE_LIST, "vortex")):
		if not frappe.db.exists("Item Price", {"item_code": PODDON_ITEM, "price_list": pl}):
			frappe.get_doc({"doctype": "Item Price", "item_code": PODDON_ITEM, "price_list": pl,
			                "uom": PODDON_UOM, "currency": CURRENCY, "price_list_rate": PODDON_NARX[key]}).insert()
			n += 1
	print(f"  Item Price: {n} ta yangi")


# Vortex rollari ishlashi uchun zarur ma'lumotnomalarga o'qish huquqi. Bularsiz
# formadagi Link maydonlar (Mijoz, Tovar, UOM...) validate_link da rad etiladi,
# ofis esa PI/SI yaratayotganda Account o'qiy olmaydi (ERPNext get_party_account
# buni ignore_permissions bilan ham chetlab o'tmaydi).
ROLE_READ = {
	"Vortex Manager": ["Customer", "Item", "UOM", "Company"],
	"Vortex Ofis": ["Customer", "Item", "UOM", "Company", "Supplier", "Account", "Cost Center"],
}


def create_roles():
	from frappe.permissions import add_permission

	for role in ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert()
			print(f"  Role: {role}")
	for role, doctypes in ROLE_READ.items():
		for doctype in doctypes:
			if frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": role, "permlevel": 0}):
				continue
			add_permission(doctype, role, 0)
			print(f"  {role} -> {doctype}: read")


# --------------------------------------------------------- 1-versiya izlari

def teardown_v1():
	"""Birinchi urinishdan qolgan Workflow, Sozlamalar, Buyurtma doctypelarini o'chiradi."""
	frappe.flags.in_migrate = True
	for doctype, name in (
		("Workflow", "Vortex Buyurtma"),
		("Report", "Vortex Buyurtmalar Reestri"),
		("DocType", "Vortex Buyurtma"),
		("DocType", "Vortex Buyurtma Tovar"),
		("DocType", "Vortex Sozlamalari"),
	):
		if frappe.db.exists(doctype, name):
			if doctype == "Report":
				frappe.db.set_value("Report", name, "is_standard", "No")
			frappe.delete_doc(doctype, name, force=1, ignore_permissions=True)
			print(f"  eski o'chirildi: {doctype} {name}")
	for ip in frappe.get_all("Item Price", {"item_code": ESKI_YETKAZISH_ITEM}, pluck="name"):
		frappe.delete_doc("Item Price", ip, force=1, ignore_permissions=True)
	if frappe.db.exists("Item", ESKI_YETKAZISH_ITEM):
		frappe.delete_doc("Item", ESKI_YETKAZISH_ITEM, force=1, ignore_permissions=True)
		print(f"  eski o'chirildi: Item {ESKI_YETKAZISH_ITEM}")
	frappe.flags.in_migrate = False
