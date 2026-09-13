// Copyright (c) 2026, Asadbek and contributors
// License: see license.txt

const VZ_DEF = "akfa_accounting.vortex_narx.qator_defaults";
const VZ_RANG = { "Yangi": "gray", "Qabul qilindi": "blue", "Qisman jo'natildi": "orange", "Completed": "green", "Bekor": "red" };

frappe.ui.form.on("Vortex Zayavka", {
	setup(frm) {
		frm.set_query("uom", "tovarlar", (doc, cdt, cdn) => {
			const row = locals[cdt][cdn];
			return { query: "akfa_accounting.vortex_narx.item_uom_query", filters: { item: row.item } };
		});
		// Obyekt — faqat tanlangan mijozniki
		frm.set_query("obyekt", () => ({ filters: { customer: frm.doc.customer || "" } }));
	},

	onload(frm) {
		// Frappe Link maydonga user/global default kompaniyani (AKFA) docfield
		// default'idan ustun qo'yadi -- yangi zayavka doim Vortex bilan ochilsin.
		// Maydon tahrirlanadi: manager kerak bo'lsa keyin o'zgartiradi.
		if (frm.is_new() && !frm.doc.amended_from) frm.set_value("company", "Vortex");
	},

	customer(frm) {
		if (frm.doc.obyekt) frm.set_value("obyekt", "");
	},

	refresh(frm) {
		if (frm.doc.holat) frm.page.set_indicator(__(frm.doc.holat), VZ_RANG[frm.doc.holat] || "gray");

		const ochiq = frm.doc.docstatus === 1 && !["Completed", "Bekor"].includes(frm.doc.holat);
		if (ochiq && frappe.model.can_create("Vortex Jonatuv")) {
			frm.add_custom_button(__("Jo'natuv yaratish"), () => {
				frappe.model.open_mapped_doc({
					method: "akfa_accounting.akfa_accounting.doctype.vortex_zayavka.vortex_zayavka.make_jonatuv",
					frm,
				});
			}).addClass("btn-primary");
		}
	},
});

frappe.ui.form.on("Vortex Zayavka Tovar", {
	item(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.item) return;
		frappe.call({ method: VZ_DEF, args: { item: row.item }, callback(r) {
			if (!r.message) return;
			const v = { uom: r.message.uom, conversion_factor: r.message.conversion_factor };
			if (!flt(row.vortex_narx)) v.vortex_narx = r.message.vortex_narx;
			frappe.model.set_value(cdt, cdn, v).then(() => vz_qator_summa(frm, cdt, cdn));
		}});
	},
	uom(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.item || !row.uom) { vz_jami(frm); return; }
		frappe.call({ method: VZ_DEF, args: { item: row.item, uom: row.uom }, callback(r) {
			if (!r.message) { vz_jami(frm); return; }
			const v = { conversion_factor: r.message.conversion_factor, vortex_narx: r.message.vortex_narx };
			frappe.model.set_value(cdt, cdn, v).then(() => vz_qator_summa(frm, cdt, cdn));
		}});
	},
	qty(frm, cdt, cdn) { vz_qator_summa(frm, cdt, cdn); },
	vortex_narx(frm, cdt, cdn) { vz_qator_summa(frm, cdt, cdn); },
	tovarlar_remove(frm) { vz_jami(frm); },
});


function vz_qator_summa(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	frappe.model
		.set_value(cdt, cdn, "vortex_summa", flt(row.qty) * flt(row.vortex_narx))
		.then(() => vz_jami(frm));
}

// vz_jami() avval chaqirilardi-yu, hech qayerda e'lon qilinmagan edi (JS xatosi).
function vz_jami(frm) {
	const rows = frm.doc.tovarlar || [];
	frm.set_value({
		jami_olcham: vortex_jami_olcham(rows),
		vortex_jami: rows.reduce((a, r) => a + flt(r.vortex_summa), 0),
	});
}


function vortex_jami_olcham(rows) {
	const y = {};
	(rows || []).forEach((r) => { if (r.uom && flt(r.qty)) y[r.uom] = (y[r.uom] || 0) + flt(r.qty); });
	const son = (x) => String(Math.round(x * 1000) / 1000);
	return Object.entries(y).map(([u, q]) => `${son(q)} ${u}`).join(" + ");
}
