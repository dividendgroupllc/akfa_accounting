// Copyright (c) 2026, Asadbek and contributors
// License: see license.txt

const VJ_DEF = "akfa_accounting.vortex_narx.qator_defaults";

frappe.ui.form.on("Vortex Jonatuv", {
	setup(frm) {
		frm.set_query("uom", "tovarlar", (doc, cdt, cdn) => {
			const row = locals[cdt][cdn];
			return { query: "akfa_accounting.vortex_narx.item_uom_query", filters: { item: row.item } };
		});
		frm.set_query("zayavka", () => ({ filters: { docstatus: 1, holat: ["not in", ["Completed", "Bekor"]] } }));
		frm.set_query("supplier", () => ({ filters: { disabled: 0 } }));
	},

	onload(frm) {
		// Amend: Frappe amend paytida no_copy maydonlarni ham ko'chiradi -> bekor qilingan
		// PI/SI havolasi yangi hujjatga o'tib, "Cannot link cancelled document" beradi.
		if (frm.is_new() && frm.doc.amended_from) {
			frm.doc.purchase_invoice = null;
			frm.doc.sales_invoice = null;
			frm.doc.qabul_holati = "Kutilmoqda";
			frm.doc.qabul_qilgan = null;
			frm.doc.qabul_sana = null;
		}
	},

	refresh(frm) {
		if (frm.doc.docstatus === 0) frm.page.set_indicator(__("Qoralama"), "gray");
		else if (frm.doc.docstatus === 2) frm.page.set_indicator(__("Bekor"), "red");
		else if (frm.doc.qabul_holati === "Qabul qilindi") frm.page.set_indicator(__("Qabul qilindi"), "green");
		else frm.page.set_indicator(__("Jo'natildi — qabul kutilmoqda"), "orange");

		if (frm.doc.docstatus === 1 && frm.doc.qabul_holati !== "Qabul qilindi") {
			frm.add_custom_button(__("Qabul qildim"), () => {
				frappe.confirm(__("Molni qabul qilganingizni tasdiqlaysizmi?"), () => {
					frm.call("qabul_qildim").then(() => {
						frappe.show_alert({ message: __("Qabul qilindi"), indicator: "green" });
						frm.reload_doc();
					});
				});
			}).addClass("btn-primary");
		}
	},
});

frappe.ui.form.on("Vortex Jonatuv Tovar", {
	item(frm, cdt, cdn) { vj_defaults(frm, cdt, cdn, true); },
	uom(frm, cdt, cdn) { vj_defaults(frm, cdt, cdn, true); },
	qty(frm, cdt, cdn) { vj_summa(frm, cdt, cdn); },
	vortex_narx(frm, cdt, cdn) { vj_summa(frm, cdt, cdn); },
	zavod_narx(frm, cdt, cdn) { vj_summa(frm, cdt, cdn); },
	tovarlar_remove(frm) { vj_jami(frm); },
});

function vj_defaults(frm, cdt, cdn, narxni_yangila) {
	const row = locals[cdt][cdn];
	if (!row.item) return;
	frappe.call({
		method: VJ_DEF,
		args: { item: row.item, uom: row.uom || undefined },
		callback(r) {
			if (!r.message) return;
			const n = r.message;
			const v = { conversion_factor: n.conversion_factor };
			if (!row.uom) v.uom = n.uom;
			// Sotuv narxi zayavkadan keladi — zayavkaga bog'langan qatorda unga tegilmaydi.
			// Qo'lda qo'shilgan qatorda (poddon, salafan...) Item Price'dan to'ldiramiz.
			if (!row.zayavka_qator && (narxni_yangila || !row.vortex_narx)) v.vortex_narx = n.vortex_narx;
			if (n.zavod_narx !== undefined && (narxni_yangila || !row.zavod_narx)) v.zavod_narx = n.zavod_narx;
			frappe.model.set_value(cdt, cdn, v).then(() => vj_summa(frm, cdt, cdn));
		},
	});
}

function vj_summa(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	const v = { vortex_summa: flt(row.qty) * flt(row.vortex_narx) };
	if (row.zavod_narx !== undefined) {
		v.zavod_summa = flt(row.qty) * flt(row.zavod_narx);
		v.foyda = v.vortex_summa - v.zavod_summa;
	}
	frappe.model.set_value(cdt, cdn, v).then(() => vj_jami(frm));
}

function vj_jami(frm) {
	const rows = frm.doc.tovarlar || [];
	const sum = (f) => rows.reduce((a, r) => a + flt(r[f]), 0);
	const v = { vortex_jami: sum("vortex_summa"), jami_olcham: vortex_jami_olcham(rows) };
	if (rows.some((r) => r.zavod_summa !== undefined)) {
		v.zavod_jami = sum("zavod_summa");
		v.foyda_jami = v.vortex_jami - v.zavod_jami;
	}
	frm.set_value(v);
}

function vortex_jami_olcham(rows) {
	const y = {};
	(rows || []).forEach((r) => { if (r.uom && flt(r.qty)) y[r.uom] = (y[r.uom] || 0) + flt(r.qty); });
	const son = (x) => String(Math.round(x * 1000) / 1000);
	return Object.entries(y).map(([u, q]) => `${son(q)} ${u}`).join(" + ");
}
