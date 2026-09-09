# Copyright (c) 2026, Asadbek and contributors
# For license information, please see license.txt

"""Kassa Dashboard — kassalar qoldig'i, kassalararo oqim, kirim manbalari va
osilib yotgan qoldiqlar.

Barcha raqamlar `GL Entry` dan olinadi — ya'ni hujjat turi (Payment Entry,
Journal Entry, Kassa Rasxod'dan tug'ilgan JE) nima bo'lishidan qat'i nazar,
bitta manbadan. Shuning uchun dashboard bosh daftar bilan tiyin-tiyin mos keladi.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate

# Kontragent qoldiqlari shu schot turlarida yotadi
OSILGAN_TURLARI = ("Payable", "Receivable")

# Himoya chegaralari
MURAKKAB_LIMIT = 50           # matritsaga kirmagan hujjatlardan nechtasi ko'rsatiladi
OQIM_QATOR_LIMITI = 60000     # oqim tahlili uchun eng ko'p GL qatori


def _kassa_accounts():
	"""Barcha naqd kassa schotlari (guruh emas), tartib bilan."""
	return frappe.get_all(
		"Account",
		filters={"account_type": "Cash", "is_group": 0, "disabled": 0},
		fields=["name", "account_name", "account_number", "account_currency"],
		order_by="account_number asc, name asc",
	)


def _egasi(account_name):
	"""'Наличные USD Azimov' -> 'Azimov'. Egasi topilmasa nomning o'zi qaytadi."""
	tokens = [t for t in (account_name or "").split() if t]
	skip = {"наличные", "наличный", "usd", "uzs", "eur", "rub"}
	qolgan = [t for t in tokens if t.lower() not in skip]
	return " ".join(qolgan) if qolgan else (account_name or "")


def _sana_oraligi(filters):
	from_date = getdate(filters.get("from_date"))
	to_date = getdate(filters.get("to_date"))
	if from_date > to_date:
		frappe.throw(_("Boshlanish sanasi tugash sanasidan katta bo'lishi mumkin emas"))
	return from_date, to_date


# ============================ 1. KASSALAR QOLDIG'I ============================

def _kassalar(accounts, from_date, to_date, tanlangan):
	"""Har kassa uchun: boshlang'ich qoldiq, davr kirimi/chiqimi, oxirgi qoldiq."""
	if not tanlangan:
		return []

	names = [a["name"] for a in tanlangan]
	ph = ", ".join(["%s"] * len(names))
	rows = frappe.db.sql(
		f"""
		SELECT account,
		       SUM(CASE WHEN posting_date < %s
		                THEN debit_in_account_currency - credit_in_account_currency
		                ELSE 0 END) AS boshlangich,
		       SUM(CASE WHEN posting_date BETWEEN %s AND %s
		                THEN debit_in_account_currency ELSE 0 END) AS kirim,
		       SUM(CASE WHEN posting_date BETWEEN %s AND %s
		                THEN credit_in_account_currency ELSE 0 END) AS chiqim
		FROM `tabGL Entry`
		WHERE is_cancelled = 0 AND posting_date <= %s AND account IN ({ph})
		GROUP BY account
		""",
		(from_date, from_date, to_date, from_date, to_date, to_date, *names),
		as_dict=True,
	)
	by_acc = {r.account: r for r in rows}

	natija = []
	for a in tanlangan:
		r = by_acc.get(a["name"])
		boshlangich = flt(r.boshlangich) if r else 0.0
		kirim = flt(r.kirim) if r else 0.0
		chiqim = flt(r.chiqim) if r else 0.0
		natija.append({
			"account": a["name"],
			"raqam": a["account_number"] or "",
			"nomi": a["account_name"],
			"egasi": _egasi(a["account_name"]),
			"valyuta": a["account_currency"],
			"boshlangich": boshlangich,
			"kirim": kirim,
			"chiqim": chiqim,
			"oxirgi": boshlangich + kirim - chiqim,
		})
	return natija


# ===================== 2. KASSALARARO O'TKAZMALAR MATRITSASI ==================

def _kassa_qatorlari(kassa_names, from_date, to_date):
	"""Davr ichida kamida ikki xil kassa schotiga tegqan hujjatlarning kassa qatorlari."""
	ph = ", ".join(["%s"] * len(kassa_names))
	return frappe.db.sql(
		f"""
		SELECT g.voucher_type, g.voucher_no, g.account, g.posting_date,
		       g.debit_in_account_currency AS d, g.credit_in_account_currency AS c
		FROM `tabGL Entry` g
		WHERE g.is_cancelled = 0
		  AND g.posting_date BETWEEN %s AND %s
		  AND g.account IN ({ph})
		  AND g.voucher_no IN (
		        SELECT voucher_no FROM `tabGL Entry`
		        WHERE is_cancelled = 0 AND posting_date BETWEEN %s AND %s
		          AND account IN ({ph})
		        GROUP BY voucher_no
		        HAVING COUNT(DISTINCT account) > 1)
		ORDER BY g.posting_date, g.creation
		""",
		(from_date, to_date, *kassa_names, from_date, to_date, *kassa_names),
		as_dict=True,
	)


def _matritsa(accounts, from_date, to_date):
	"""Kassadan kassaga o'tkazmalar.

	Faqat bitta chiqim va bitta kirim qatori bo'lgan hujjat o'tkazma deb hisoblanadi.
	Bir nechta kassa qatori bir tomonga yozilgan hujjatlar (masalan Cash Distribution
	Aripovning USD va UZS schotini birga kreditlaydi) o'tkazma EMAS — ular alohida
	`murakkab` ro'yxatiga chiqadi, jimgina tashlab yuborilmaydi.
	"""
	kassa_names = [a["name"] for a in accounts]
	if not kassa_names:
		return [], {"royxat": [], "jami": 0}

	rows = _kassa_qatorlari(kassa_names, from_date, to_date)
	meta = {a["name"]: a for a in accounts}

	by_voucher = {}
	for r in rows:
		by_voucher.setdefault((r.voucher_type, r.voucher_no), []).append(r)

	juftlar, murakkab = {}, []
	for (vt, vn), rs in by_voucher.items():
		chiqimlar = [r for r in rs if flt(r.c) > 0]
		kirimlar = [r for r in rs if flt(r.d) > 0]

		if len(chiqimlar) == 1 and len(kirimlar) == 1:
			o, i = chiqimlar[0], kirimlar[0]
			if o.account == i.account:
				continue
			kalit = (o.account, i.account)
			agg = juftlar.setdefault(kalit, {"soni": 0, "summa": 0.0, "oxirgi": None})
			agg["soni"] += 1
			agg["summa"] += flt(o.c)
			agg["oxirgi"] = max(agg["oxirgi"], o.posting_date) if agg["oxirgi"] else o.posting_date
		else:
			# Bunday hujjatda turli valyutadagi kassa qatorlari bo'lishi mumkin
			# (masalan Cash Distribution Aripovning USD va UZS schotini birga kreditlaydi),
			# shuning uchun summa valyuta kesimida ajratiladi — aks holda dollar va so'm
			# bitta songa qo'shilib, ma'nosiz raqam chiqadi.
			val_summa = {}
			for r in rs:
				v = meta[r.account]["account_currency"]
				val_summa[v] = val_summa.get(v, 0.0) + (flt(r.c) or flt(r.d))
			murakkab.append({
				"voucher_type": vt, "voucher_no": vn,
				"sana": rs[0].posting_date,
				"chiqim_soni": len(chiqimlar), "kirim_soni": len(kirimlar),
				"summalar": [
					{"valyuta": v, "summa": sm}
					for v, sm in sorted(val_summa.items(), key=lambda x: -x[1])
				],
			})

	natija = []
	for (f, t), v in juftlar.items():
		natija.append({
			"qayerdan": _egasi(meta[f]["account_name"]),
			"qayerdan_account": f,
			"qayerga": _egasi(meta[t]["account_name"]),
			"qayerga_account": t,
			"valyuta": meta[f]["account_currency"],
			"valyuta_qabul": meta[t]["account_currency"],
			"soni": v["soni"],
			"summa": v["summa"],
			"oxirgi": v["oxirgi"],
		})
	natija.sort(key=lambda x: (-x["summa"]))
	murakkab.sort(key=lambda x: x["sana"], reverse=True)
	# Ro'yxat kesiladi, lekin HAQIQIY soni ham qaytariladi — "hech narsa
	# jimgina tashlanmaydi" va'dasi kesilgan sondan emas, to'liq sondan kelib chiqadi.
	return natija, {"royxat": murakkab[:MURAKKAB_LIMIT], "jami": len(murakkab)}


# ==================== 3. KIRIM MANBALARI / CHIQIM YO'NALISHLARI ==============

def _tasnif(qarshi_qatorlar, kassa_meta):
	"""Hujjatning qarama-qarshi qatorlariga qarab manba/yo'nalishni nomlaydi.

	`against` maydoniga tayanib bo'lmaydi: kontragentli qatorlarda u schot emas,
	kontragent NOMINI saqlaydi — shuning uchun hujjatning o'z qatorlari o'qiladi."""
	for r in qarshi_qatorlar:
		if r["account"] in kassa_meta:
			return f"Kassadan: {_egasi(kassa_meta[r['account']]['account_name'])}", "kassa"

	for r in qarshi_qatorlar:
		if r["party_type"] == "Employee":
			return "Podochot qaytimi", "podochot"

	turlar = {r["account_type"] for r in qarshi_qatorlar}
	if "Temporary" in turlar:
		return "Boshlang'ich qoldiq", "opening"
	if "Receivable" in turlar:
		return "Mijozlardan", "mijoz"
	if "Payable" in turlar:
		return "Kontragentdan", "kontragent"

	root_lar = {r["root_type"] for r in qarshi_qatorlar}
	if "Income" in root_lar:
		return "Daromad", "daromad"
	if "Expense" in root_lar:
		return "Xarajat", "xarajat"
	if "Equity" in root_lar:
		return "Dividend / kapital", "kapital"

	nom = qarshi_qatorlar[0]["account_name"] if qarshi_qatorlar else "Aniqlanmagan"
	return nom, "boshqa"


def _kassa_qatorlar_soni(kassa_names, from_date, to_date):
	"""Davrda kassa schotlariga tegqan GL qatorlari soni — og'irlikni oldindan o'lchash."""
	ph = ", ".join(["%s"] * len(kassa_names))
	return frappe.db.sql(
		f"""SELECT COUNT(*) FROM `tabGL Entry`
		    WHERE is_cancelled = 0 AND posting_date BETWEEN %s AND %s
		      AND account IN ({ph})""",
		(from_date, to_date, *kassa_names),
	)[0][0]


def _oqim(accounts, from_date, to_date, tanlangan):
	"""Har kassa uchun kirim manbalari va chiqim yo'nalishlari."""
	if not tanlangan:
		return [], []

	kassa_meta = {a["name"]: a for a in accounts}
	names = [a["name"] for a in tanlangan]
	ph = ", ".join(["%s"] * len(names))

	kassa_qatorlar = frappe.db.sql(
		f"""
		SELECT voucher_type, voucher_no, account,
		       debit_in_account_currency AS d, credit_in_account_currency AS c
		FROM `tabGL Entry`
		WHERE is_cancelled = 0 AND posting_date BETWEEN %s AND %s AND account IN ({ph})
		""",
		(from_date, to_date, *names),
		as_dict=True,
	)
	if not kassa_qatorlar:
		return [], []

	# Hujjatlarning BARCHA qatorlari — tasnif shular asosida qilinadi
	voucher_nos = list({r.voucher_no for r in kassa_qatorlar})
	hammasi = {}
	for chunk_start in range(0, len(voucher_nos), 500):
		chunk = voucher_nos[chunk_start:chunk_start + 500]
		for r in frappe.db.sql(
			"""
			SELECT g.voucher_no, g.account, g.party_type, g.party,
			       g.debit_in_account_currency AS d, g.credit_in_account_currency AS c,
			       a.account_type, a.root_type, a.account_name
			FROM `tabGL Entry` g JOIN `tabAccount` a ON a.name = g.account
			WHERE g.is_cancelled = 0 AND g.voucher_no IN %s
			""",
			(chunk,), as_dict=True,
		):
			hammasi.setdefault(r.voucher_no, []).append(r)

	# Payment Entry turi — "Mijozlardan" ni aniq ajratish uchun
	pe_nos = [r.voucher_no for r in kassa_qatorlar if r.voucher_type == "Payment Entry"]
	pe_turi = {}
	if pe_nos:
		for e in frappe.db.sql(
			"""SELECT name, payment_type, paid_from, party_type
			   FROM `tabPayment Entry` WHERE name IN %s""",
			(list(set(pe_nos)),), as_dict=True,
		):
			pe_turi[e.name] = e

	kirim_agg, chiqim_agg = {}, {}
	for r in kassa_qatorlar:
		kirimmi = flt(r.d) > 0
		summa = flt(r.d) if kirimmi else flt(r.c)
		if not summa:
			continue

		nom = None
		pe = pe_turi.get(r.voucher_no)
		if pe and pe.payment_type == "Receive" and pe.party_type == "Customer":
			nom = "Mijozlardan"
		elif pe and pe.payment_type == "Internal Transfer":
			boshqa = pe.paid_from if kirimmi else None
			if kirimmi and boshqa in kassa_meta:
				nom = f"Kassadan: {_egasi(kassa_meta[boshqa]['account_name'])}"

		if nom is None:
			# qarama-qarshi tomon: kirim bo'lsa kreditlangan qatorlar, aksincha debet
			qarshi = [
				x for x in hammasi.get(r.voucher_no, [])
				if x.account != r.account and (flt(x.c) > 0 if kirimmi else flt(x.d) > 0)
			]
			nom, _turi = _tasnif(qarshi, kassa_meta)
			if not kirimmi and nom.startswith("Kassadan: "):
				nom = "Kassaga: " + nom[len("Kassadan: "):]

		agg = kirim_agg if kirimmi else chiqim_agg
		kalit = (r.account, nom)
		hozir = agg.setdefault(kalit, {"soni": 0, "summa": 0.0})
		hozir["soni"] += 1
		hozir["summa"] += summa

	def _royxat(agg):
		out = []
		for (acc, nom), v in agg.items():
			out.append({
				"kassa": _egasi(kassa_meta[acc]["account_name"]),
				"account": acc,
				"valyuta": kassa_meta[acc]["account_currency"],
				"nom": nom,
				"soni": v["soni"],
				"summa": v["summa"],
			})
		out.sort(key=lambda x: (x["kassa"], x["valyuta"], -x["summa"]))
		return out

	return _royxat(kirim_agg), _royxat(chiqim_agg)


# ======================= 4. OSILIB YOTGAN QOLDIQLAR ==========================

def _osilgan(to_date, limit=8):
	"""Kontragentli schotlardagi qoldiqlar — sana holatiga (kumulativ).

	Bu davr bilan cheklanmaydi: osilgan qarz davr boshidan oldin paydo bo'lgan
	bo'lsa ham ko'rinishi kerak.

	Schot va kontragent kesimi BITTA so'rovda olinadi — har schot uchun alohida
	so'rov yuborilsa, schot soni o'sganda so'rovlar soni ham o'sib ketardi."""
	qatorlar = frappe.db.sql(
		"""
		SELECT g.account, g.party, g.party_type,
		       a.account_type, a.account_currency, a.account_name,
		       SUM(g.debit_in_account_currency - g.credit_in_account_currency) AS qoldiq
		FROM `tabGL Entry` g
		JOIN `tabAccount` a ON a.name = g.account
		WHERE g.is_cancelled = 0 AND g.posting_date <= %s AND a.account_type IN %s
		GROUP BY g.account, g.party, g.party_type,
		         a.account_type, a.account_currency, a.account_name
		""",
		(to_date, OSILGAN_TURLARI),
		as_dict=True,
	)

	schotlar = {}
	for r in qatorlar:
		s = schotlar.setdefault(r.account, {
			"account": r.account, "nomi": r.account_name, "turi": r.account_type,
			"valyuta": r.account_currency, "qoldiq": 0.0, "tomonlar": set(), "party_lar": [],
		})
		s["qoldiq"] += flt(r.qoldiq)
		if r.party:
			s["tomonlar"].add(r.party)
		if abs(flt(r.qoldiq)) > 0.005:
			s["party_lar"].append({
				"party": r.party, "party_type": r.party_type, "qoldiq": flt(r.qoldiq),
			})

	natija = []
	for s in schotlar.values():
		if not flt(s["qoldiq"]):
			continue
		s["party_lar"].sort(key=lambda t: abs(t["qoldiq"]), reverse=True)
		natija.append({
			"account": s["account"], "nomi": s["nomi"], "turi": s["turi"],
			"valyuta": s["valyuta"], "tomonlar": len(s["tomonlar"]),
			"qoldiq": s["qoldiq"], "eng_kattalar": s["party_lar"][:limit],
		})
	natija.sort(key=lambda x: abs(x["qoldiq"]), reverse=True)
	return natija


# ================================ KIRISH NUQTASI =============================

@frappe.whitelist()
def get_dashboard_data(from_date, to_date, valyuta=None, kassa=None):
	"""Dashboard uchun barcha bo'limlarni bitta so'rovda qaytaradi."""
	# Bu yerda kassa qoldig'i, kontragent qarzlari va butun pul oqimi qaytariladi.
	# Sahifadagi rol ro'yxati faqat UI ni yopadi — API ni alohida qo'riqlash kerak,
	# aks holda istalgan tizimga kirgan foydalanuvchi moliyaviy manzarani ko'radi.
	if not frappe.has_permission("GL Entry", "read"):
		frappe.throw(
			_("Kassa Dashboard uchun ruxsat yo'q (GL Entry o'qish huquqi kerak)"),
			frappe.PermissionError,
		)

	filters = {"from_date": from_date, "to_date": to_date}
	from_date, to_date = _sana_oraligi(filters)

	accounts = _kassa_accounts()
	if not accounts:
		return {"kassalar": [], "matritsa": [], "murakkab": [],
		        "kirim_manbalari": [], "chiqim_yonalishlari": [], "osilgan": []}

	# Filtrlar faqat KO'RSATISHNI cheklaydi; matritsa esa barcha kassalar ustida
	# hisoblanadi, aks holda yarim o'tkazma ko'rinib, summa noto'g'ri chiqadi.
	tanlangan = accounts
	if valyuta:
		tanlangan = [a for a in tanlangan if a["account_currency"] == valyuta]
	if kassa:
		tanlangan = [a for a in tanlangan if _egasi(a["account_name"]) == kassa]

	# Qoldiqlar SQL yig'indisi bilan hisoblanadi va qanchalik uzoq davr bo'lsa ham
	# arzon. Oqim tahlili esa hujjatlarni qatorma-qator o'qiydi — juda keng oraliqda
	# (masalan "boshidan bugungacha") u butun bosh daftarni xotiraga tortib kelardi.
	# Shuning uchun og'irlik oldindan o'lchanadi: chegaradan oshsa qoldiqlar baribir
	# ko'rsatiladi, oqim bo'limlari esa ochiq ogohlantirish bilan o'tkazib yuboriladi.
	kassa_names = [a["name"] for a in accounts]
	qatorlar_soni = _kassa_qatorlar_soni(kassa_names, from_date, to_date)
	ogir = qatorlar_soni > OQIM_QATOR_LIMITI

	if ogir:
		matritsa, murakkab = [], {"royxat": [], "jami": 0}
	else:
		matritsa, murakkab = _matritsa(accounts, from_date, to_date)
	if valyuta:
		matritsa = [m for m in matritsa if m["valyuta"] == valyuta]
	if kassa:
		matritsa = [m for m in matritsa if kassa in (m["qayerdan"], m["qayerga"])]

	osilgan = _osilgan(to_date)
	if valyuta:
		osilgan = [o for o in osilgan if o["valyuta"] == valyuta]

	kirim_manbalari, chiqim_yonalishlari = (
		([], []) if ogir else _oqim(accounts, from_date, to_date, tanlangan)
	)

	return {
		"ogohlantirish": (
			_("Танланган давр жуда катта ({0} сатр) — қолдиқлар кўрсатилди, "
			  "пул ҳаракати ва ўтказмалар таҳлили ўтказиб юборилди. "
			  "Санани торайтиринг.").format(qatorlar_soni)
			if ogir else None
		),
		"kassalar": _kassalar(accounts, from_date, to_date, tanlangan),
		"matritsa": matritsa,
		"murakkab": murakkab,
		"kirim_manbalari": kirim_manbalari,
		"chiqim_yonalishlari": chiqim_yonalishlari,
		"osilgan": osilgan,
		"egalar": sorted({_egasi(a["account_name"]) for a in accounts}),
		"valyutalar": sorted({a["account_currency"] for a in accounts}),
		"davr": {"from_date": str(from_date), "to_date": str(to_date)},
	}
