frappe.pages['kassa-dashboard'].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Kassa Dashboard",
		single_column: true,
	});
	new KassaDashboard(page);
};

class KassaDashboard {
	constructor(page) {
		this.page = page;
		this.inject_styles();
		this.make_filters();
		this.$body = $('<div class="kd-body"></div>').appendTo(this.page.main);
		this.refresh();
	}

	// ---------------------------------------------------------------- filtrlar
	make_filters() {
		const oy_boshi = frappe.datetime.month_start();
		const bugun = frappe.datetime.get_today();

		this.f_from = this.page.add_field({
			fieldname: "from_date", label: "Дан", fieldtype: "Date", default: oy_boshi,
			change: () => this.refresh(),
		});
		this.f_to = this.page.add_field({
			fieldname: "to_date", label: "Гача", fieldtype: "Date", default: bugun,
			change: () => this.refresh(),
		});
		this.f_cur = this.page.add_field({
			fieldname: "valyuta", label: "Валюта", fieldtype: "Select", options: ["", "USD", "UZS"],
			change: () => this.refresh(),
		});
		this.f_kassa = this.page.add_field({
			fieldname: "kassa", label: "Касса", fieldtype: "Select", options: [""],
			change: () => this.refresh(),
		});

		this.f_from.set_input(oy_boshi);
		this.f_to.set_input(bugun);

		this.page.set_primary_action("Янгилаш", () => this.refresh(), "refresh");
		this.page.add_menu_item("Жорий ой", () => this.set_range(frappe.datetime.month_start(), bugun));
		this.page.add_menu_item("Жорий йил", () => this.set_range(frappe.datetime.year_start(), bugun));
		this.page.add_menu_item("Бошидан бугунгача", () => this.set_range("2000-01-01", frappe.datetime.get_today()));
	}

	set_range(from, to) {
		this.f_from.set_input(from);
		this.f_to.set_input(to);
		this.refresh();
	}

	get_filters() {
		return {
			from_date: this.f_from.get_value(),
			to_date: this.f_to.get_value(),
			valyuta: this.f_cur.get_value() || null,
			kassa: this.f_kassa.get_value() || null,
		};
	}

	// ------------------------------------------------------------------ yuklash
	refresh() {
		const filters = this.get_filters();
		if (!filters.from_date || !filters.to_date) return;

		this.$body.html('<div class="kd-loading">Юкланмоқда…</div>');
		frappe.call({
			method: "akfa_accounting.akfa_accounting.api.kassa_dashboard.get_dashboard_data",
			args: filters,
			callback: (r) => {
				if (!r.message) return;
				this.data = r.message;
				this.sync_kassa_options();
				this.render();
			},
			error: () => this.$body.html('<div class="kd-loading">Маълумот юкланмади</div>'),
		});
	}

	sync_kassa_options() {
		const joriy = this.f_kassa.get_value();
		const kerak = [""].concat(this.data.egalar || []);
		if (JSON.stringify(kerak) !== JSON.stringify(this._kassa_opts)) {
			this._kassa_opts = kerak;
			this.f_kassa.df.options = kerak;
			this.f_kassa.refresh();
			if (joriy) this.f_kassa.set_input(joriy);
		}
	}

	// ------------------------------------------------------------------ helpers
	fmt(v, cur) {
		return format_currency(v, cur, cur === "UZS" ? 0 : 2);
	}

	link(dt, dn, label) {
		return `<a href="/app/${frappe.router.slug(dt)}/${encodeURIComponent(dn)}">${frappe.utils.escape_html(label || dn)}</a>`;
	}

	esc(s) {
		return frappe.utils.escape_html(s == null ? "" : String(s));
	}

	// ------------------------------------------------------------------- render
	render() {
		const d = this.data;
		const ogoh = d.ogohlantirish
			? `<div class="kd-ogoh">${this.esc(d.ogohlantirish)}</div>` : "";
		this.$body.html([
			ogoh,
			this.render_kassalar(d.kassalar),
			this.render_matritsa(d.matritsa),
			this.render_oqim(d.kirim_manbalari, d.chiqim_yonalishlari),
			this.render_osilgan(d.osilgan),
			this.render_murakkab(d.murakkab),
		].join(""));
	}

	// ulush chizig'i — bo'sh joyni raqamning "og'irligi" bilan to'ldiradi
	bar(qism, jami, sinf) {
		const p = jami ? Math.max(1.5, (Math.abs(qism) / Math.abs(jami)) * 100) : 0;
		return `<span class="kd-bar"><i class="${sinf}" style="width:${Math.min(p, 100)}%"></i></span>`;
	}

	// 1) kassalar
	render_kassalar(kassalar) {
		const faol = (kassalar || []).filter((k) => k.boshlangich || k.kirim || k.chiqim || k.oxirgi);
		if (!faol.length) return this.bosh("Кассалар ҳолати", "Танланган даврда ҳаракат йўқ");

		const cards = faol.map((k) => {
			const eng = Math.max(Math.abs(k.kirim), Math.abs(k.chiqim)) || 1;
			const nol = Math.abs(k.oxirgi) < 0.005;
			const holat = nol ? "kd-zero" : k.oxirgi > 0 ? "" : "kd-neg";
			const ozgarish = k.kirim - k.chiqim;
			const belgi = ozgarish > 0 ? "+" : ozgarish < 0 ? "−" : "";
			return `
			<div class="kd-card">
				<div class="kd-card-head">
					<span class="kd-owner">${this.esc(k.egasi)}</span>
					<span class="kd-cur">${this.esc(k.valyuta)}</span>
				</div>
				<div class="kd-final ${holat}">${this.fmt(k.oxirgi, k.valyuta)}</div>
				<div class="kd-final-label">
					якуний қолдиқ
					${belgi ? `<span class="${ozgarish > 0 ? "kd-in" : "kd-out"}">${belgi}${this.fmt(Math.abs(ozgarish), k.valyuta)} даврда</span>` : ""}
				</div>
				<div class="kd-rows">
					<div class="kd-row">
						<span class="kd-k">бошланғич</span>
						<b>${this.fmt(k.boshlangich, k.valyuta)}</b>
					</div>
					<div class="kd-row kd-hasbar">
						<span class="kd-k">кирим</span>
						${this.bar(k.kirim, eng, "kd-bg-in")}
						<b class="kd-in">${this.fmt(k.kirim, k.valyuta)}</b>
					</div>
					<div class="kd-row kd-hasbar">
						<span class="kd-k">чиқим</span>
						${this.bar(k.chiqim, eng, "kd-bg-out")}
						<b class="kd-out">${this.fmt(k.chiqim, k.valyuta)}</b>
					</div>
				</div>
				<div class="kd-acc">${this.link("Account", k.account, [k.raqam, k.nomi].filter(Boolean).join(" · "))}</div>
			</div>`;
		});
		return this.section("Кассалар ҳолати", `<div class="kd-cards">${cards.join("")}</div>`);
	}

	// 2) kassalararo oqim — valyuta bo'yicha guruhlangan, ulush chizig'i bilan
	render_matritsa(matritsa) {
		if (!matritsa || !matritsa.length)
			return this.bosh("Кассалараро ўтказмалар", "Даврда кассадан кассага ўтказма бўлмаган");

		const valyutalar = [...new Set(matritsa.map((m) => m.valyuta))];
		const bloklar = valyutalar.map((v) => {
			const qatorlar = matritsa.filter((m) => m.valyuta === v);
			const jami = qatorlar.reduce((a, b) => a + b.summa, 0);
			const eng = Math.max(...qatorlar.map((m) => m.summa));
			const rows = qatorlar.map((m) => `
				<div class="kd-flowrow">
					<div class="kd-route">
						<b>${this.esc(m.qayerdan)}</b>
						<span class="kd-arrow">→</span>
						<b>${this.esc(m.qayerga)}</b>
					</div>
					<div class="kd-flowbar">${this.bar(m.summa, eng, "kd-bg-in")}</div>
					<div class="kd-flowsum">${this.fmt(m.summa, m.valyuta)}</div>
					<div class="kd-flowmeta">${m.soni} ўтказма · охирги ${this.esc(m.oxirgi)}</div>
				</div>`);
			return `<div class="kd-valblok">
				<div class="kd-valhead"><span>${this.esc(v)}</span><b>${this.fmt(jami, v)}</b></div>
				${rows.join("")}
			</div>`;
		});
		return this.section("Кассалараро ўтказмалар", `<div class="kd-split">${bloklar.join("")}</div>`);
	}

	// 3) pul harakati
	render_oqim(kirim, chiqim) {
		const blok = (royxat, sarlavha, sinf, bg) => {
			if (!royxat || !royxat.length)
				return `<div class="kd-half"><h4 class="kd-h4">${sarlavha}</h4><p class="kd-muted">Маълумот йўқ</p></div>`;

			// har kassa+valyuta guruhi ichida ulush hisoblanadi
			const jami = {};
			royxat.forEach((r) => {
				const g = r.account;
				jami[g] = (jami[g] || 0) + r.summa;
			});

			let joriy = null;
			const html = royxat.map((r) => {
				const kalit = r.account;
				let head = "";
				if (kalit !== joriy) {
					joriy = kalit;
					head = `<div class="kd-grouphead"><span>${this.esc(r.kassa)} · ${this.esc(r.valyuta)}</span>
						<b>${this.fmt(jami[kalit], r.valyuta)}</b></div>`;
				}
				const ulush = jami[kalit] ? Math.round((r.summa / jami[kalit]) * 100) : 0;
				return `${head}
				<div class="kd-oqimrow">
					<div class="kd-oqimnom">${this.esc(r.nom)}<span class="kd-cnt">${r.soni}</span></div>
					<div class="kd-oqimbar">${this.bar(r.summa, jami[kalit], bg)}</div>
					<div class="kd-oqimpct">${ulush}%</div>
					<div class="kd-oqimsum ${sinf}">${this.fmt(r.summa, r.valyuta)}</div>
				</div>`;
			});
			return `<div class="kd-half"><h4 class="kd-h4">${sarlavha}</h4>${html.join("")}</div>`;
		};
		return this.section("Пул ҳаракати", `<div class="kd-split">
			${blok(kirim, "Кирим — пул қаердан келди", "kd-in", "kd-bg-in")}
			${blok(chiqim, "Чиқим — пул қаерга кетди", "kd-out", "kd-bg-out")}
		</div>`);
	}

	// 4) osilgan
	render_osilgan(osilgan) {
		if (!osilgan || !osilgan.length) return this.bosh("Контрагентлар билан ҳисоб-китоб", "Ёпилмаган қолдиқлар йўқ");

		const bloklar = osilgan.map((o) => {
			const debet = o.qoldiq > 0;
			let izoh, tamg;
			if (o.turi === "Payable") {
				izoh = debet ? "Биз олдиндан тўлаганмиз — контрагентдан мол/хизмат кутилади"
				             : "Биз қарздормиз — тўланиши керак";
				tamg = debet ? "аванс берилган" : "қарздормиз";
			} else {
				izoh = debet ? "Мижоз бизга қарздор" : "Мижоз олдиндан тўлаган — фактурага боғланмаган";
				tamg = debet ? "қарздор" : "мижоз аванси";
			}
			const eng = Math.max(...(o.eng_kattalar || [{ qoldiq: 1 }]).map((t) => Math.abs(t.qoldiq)), 1);
			const rows = (o.eng_kattalar || []).map((t) => `
				<div class="kd-partyrow">
					<div class="kd-partynom">${t.party_type ? this.link(t.party_type, t.party) : this.esc(t.party || "—")}</div>
					<div class="kd-partybar">${this.bar(t.qoldiq, eng, t.qoldiq > 0 ? "kd-bg-in" : "kd-bg-out")}</div>
					<div class="kd-partysum ${t.qoldiq > 0 ? "kd-in" : "kd-out"}">${this.fmt(t.qoldiq, o.valyuta)}</div>
				</div>`);
			return `<div class="kd-osil">
				<div class="kd-osil-head">
					<div class="kd-osil-left">
						<div class="kd-osil-nom">${this.esc(o.nomi)}</div>
						<div class="kd-osil-meta">${this.esc(o.turi)} · ${this.esc(o.valyuta)} · ${o.tomonlar} контрагент</div>
					</div>
					<div class="kd-osil-right">
						<div class="kd-osil-sum ${debet ? "kd-in" : "kd-out"}">${this.fmt(o.qoldiq, o.valyuta)}</div>
						<span class="kd-tamg ${debet ? "kd-tamg-in" : "kd-tamg-out"}">${tamg}</span>
					</div>
				</div>
				<div class="kd-osil-izoh">${izoh}</div>
				${rows.join("")}
			</div>`;
		});
		return this.section(
			"Контрагентлар билан ҳисоб-китоб",
			`<p class="kd-muted kd-note">Ҳар бир счёт бўйича ёпилмаган қолдиқ — кимга қарздормиз, ким бизга қарздор ва қаерда аванс осилиб турибди. Қолдиқлар танланган давр билан чекланмайди: бошидан бугунгача жамланади.</p>
			<div class="kd-osil-grid">${bloklar.join("")}</div>`
		);
	}

	// 5) matritsaga kirmaganlar
	render_murakkab(murakkab) {
		const royxat = (murakkab && murakkab.royxat) || [];
		const jami = (murakkab && murakkab.jami) || 0;
		if (!royxat.length) return "";
		const rows = royxat.map((m) => `
			<div class="kd-mrow">
				<span class="kd-muted kd-mono">${this.esc(m.sana)}</span>
				<span>${this.link(m.voucher_type, m.voucher_no)}</span>
				<span class="kd-muted">${m.chiqim_soni} чиқим / ${m.kirim_soni} кирим</span>
				<span class="kd-msum">${(m.summalar || []).map((x) => this.fmt(x.summa, x.valyuta)).join(" · ")}</span>
			</div>`);
		const html = `<p class="kd-muted kd-note">Бу ҳужжатларда бир нечта касса сатри бир томонга ёзилган (масалан Cash Distribution Ариповнинг USD ва UZS счётини бирга кредитлайди) — улар кассадан кассага ўтказма эмас, шунинг учун матрицага кирмаган.</p>
			${rows.join("")}
			${jami > royxat.length ? `<p class="kd-muted kd-note" style="margin-top:12px">Жами ${jami} та, шундан биринчи ${royxat.length} таси кўрсатилди.</p>` : ""}`;
		return this.section(`Матрицага кирмаган ҳужжатлар · ${jami}`, html);
	}

	// ---------------------------------------------------------------- qoliplar
	section(sarlavha, ichi) {
		return `<section class="kd-section"><h3 class="kd-h">${sarlavha}</h3>${ichi}</section>`;
	}

	bosh(sarlavha, matn) {
		return this.section(sarlavha, `<p class="kd-muted">${matn}</p>`);
	}

	inject_styles() {
		if (document.getElementById("kd-styles")) return;
		const css = `
		/* to'liq kenglik — Frappe konteyneri torligini bosib o'tamiz */
		.page-container:has(.kd-body) .container,
		body:has(.kd-body) .page-body .container {
			max-width: 1680px; padding-left: 32px; padding-right: 32px; }
		.kd-body { padding: 6px 0 60px; font-size: 15px; }
		@media (max-width: 900px) {
			.page-container:has(.kd-body) .container,
			body:has(.kd-body) .page-body .container { padding-left: 16px; padding-right: 16px; } }
		.kd-loading { padding: 48px 0; color: var(--text-muted); font-size: 15px; }
		.kd-ogoh { margin: 14px 0 0; padding: 13px 16px; border-radius: 8px; font-size: 14px;
			color: var(--kd-out); background: rgba(190,90,18,.10);
			border: 1px solid rgba(190,90,18,.28); }

		.kd-section { margin-top: 34px; }
		.kd-h { font-size: 13px; font-weight: 600; letter-spacing: .11em; text-transform: uppercase;
			color: var(--text-muted); margin: 0 0 16px; padding-bottom: 10px;
			border-bottom: 1px solid var(--border-color); }
		.kd-h4 { font-size: 15px; font-weight: 600; margin: 0 0 12px; }
		.kd-muted { color: var(--text-muted); }
		.kd-note { font-size: 13px; max-width: 92ch; margin: 0 0 14px; }
		.kd-mono { font-variant-numeric: tabular-nums; }
		.kd-in { color: var(--kd-in); }
		.kd-out { color: var(--kd-out); }

		:root { --kd-in: #12907C; --kd-out: #BE5A12; --kd-track: rgba(0,0,0,.06); }
		[data-theme="dark"] { --kd-in: #19A88F; --kd-out: #D4762A; --kd-track: rgba(255,255,255,.09); }

		.kd-bar { display: block; height: 7px; border-radius: 4px; background: var(--kd-track); overflow: hidden; }
		.kd-bar > i { display: block; height: 100%; border-radius: 4px; }
		.kd-bg-in { background: var(--kd-in); }
		.kd-bg-out { background: var(--kd-out); }

		/* --- kassalar --- */
		.kd-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
			gap: 16px; align-items: start; }
		.kd-card { background: var(--card-bg, var(--fg-color)); border: 1px solid var(--border-color);
			border-radius: 10px; padding: 20px 20px 14px; }
		.kd-card-head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 12px; }
		.kd-owner { font-weight: 600; font-size: 17px; }
		.kd-cur { font-size: 12px; font-weight: 600; letter-spacing: .07em; color: var(--text-muted);
			border: 1px solid var(--border-color); border-radius: 5px; padding: 2px 8px; }
		.kd-final { font-size: 30px; font-weight: 600; font-variant-numeric: tabular-nums;
			line-height: 1.1; letter-spacing: -.02em; }
		.kd-final.kd-neg { color: var(--red-600, #A6362A); }
		.kd-final.kd-zero { color: var(--text-muted); }
		.kd-final-label { font-size: 13px; color: var(--text-muted); margin: 4px 0 16px;
			display: flex; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
		.kd-rows { display: flex; flex-direction: column; gap: 9px;
			border-top: 1px solid var(--border-color); padding-top: 13px; }
		.kd-row { display: grid; grid-template-columns: 78px 1fr auto; gap: 12px; align-items: center; font-size: 14px; }
		.kd-row:not(.kd-hasbar) { grid-template-columns: 78px 1fr; }
		.kd-row:not(.kd-hasbar) b { text-align: right; }
		.kd-row b { font-variant-numeric: tabular-nums; font-weight: 500; white-space: nowrap; }
		.kd-k { color: var(--text-muted); font-size: 13px; }
		.kd-acc { margin-top: 14px; font-size: 12.5px; }

		/* --- kassalararo --- */
		.kd-split { display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 30px; }
		.kd-valblok { }
		.kd-valhead { display: flex; justify-content: space-between; align-items: baseline;
			font-size: 13px; letter-spacing: .07em; text-transform: uppercase; color: var(--text-muted);
			border-bottom: 1px solid var(--border-color); padding-bottom: 8px; margin-bottom: 12px; }
		.kd-valhead b { font-size: 16px; letter-spacing: normal; text-transform: none;
			color: var(--text-color); font-variant-numeric: tabular-nums; }
		.kd-flowrow { display: grid; grid-template-columns: minmax(190px, auto) 1fr auto;
			gap: 8px 16px; align-items: center; padding: 11px 0;
			border-bottom: 1px solid var(--border-color); }
		.kd-flowrow:last-child { border-bottom: none; }
		.kd-route { font-size: 15px; display: flex; align-items: center; gap: 9px; }
		.kd-arrow { color: var(--text-muted); }
		.kd-flowsum { font-size: 16px; font-weight: 600; font-variant-numeric: tabular-nums; white-space: nowrap; }
		.kd-flowmeta { grid-column: 1 / -1; font-size: 12.5px; color: var(--text-muted); margin-top: -2px; }

		/* --- pul harakati --- */
		.kd-grouphead { display: flex; justify-content: space-between; align-items: baseline;
			font-size: 12.5px; font-weight: 600; letter-spacing: .07em; text-transform: uppercase;
			color: var(--text-muted); margin: 18px 0 8px; padding-bottom: 7px;
			border-bottom: 1px solid var(--border-color); }
		.kd-grouphead:first-child { margin-top: 0; }
		.kd-grouphead b { font-size: 15px; letter-spacing: normal; text-transform: none;
			color: var(--text-color); font-variant-numeric: tabular-nums; }
		.kd-oqimrow { display: grid; grid-template-columns: minmax(150px, 1.1fr) minmax(60px, 1fr) 42px auto;
			gap: 14px; align-items: center; padding: 7px 0; font-size: 14.5px; }
		.kd-oqimnom { display: flex; align-items: center; gap: 8px; }
		.kd-cnt { font-size: 11.5px; color: var(--text-muted); background: var(--kd-track);
			border-radius: 9px; padding: 1px 7px; font-variant-numeric: tabular-nums; }
		.kd-oqimpct { font-size: 12.5px; color: var(--text-muted); text-align: right;
			font-variant-numeric: tabular-nums; }
		.kd-oqimsum { font-weight: 600; font-variant-numeric: tabular-nums; text-align: right; white-space: nowrap; }

		/* --- osilgan --- */
		.kd-osil-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
			gap: 16px; align-items: start; }
		.kd-osil { border: 1px solid var(--border-color); border-radius: 10px; padding: 18px 18px 14px;
			background: var(--card-bg, var(--fg-color)); }
		.kd-osil-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
		.kd-osil-nom { font-weight: 600; font-size: 16px; }
		.kd-osil-meta { font-size: 12.5px; color: var(--text-muted); margin-top: 3px; }
		.kd-osil-right { text-align: right; }
		.kd-osil-sum { font-size: 21px; font-weight: 600; font-variant-numeric: tabular-nums; white-space: nowrap; }
		.kd-tamg { display: inline-block; margin-top: 5px; font-size: 11px; font-weight: 600;
			letter-spacing: .05em; padding: 2px 8px; border-radius: 5px; }
		.kd-tamg-in { color: var(--kd-in); background: rgba(18,144,124,.12); }
		.kd-tamg-out { color: var(--kd-out); background: rgba(190,90,18,.12); }
		.kd-osil-izoh { font-size: 13px; color: var(--text-muted); margin: 12px 0 12px;
			padding-top: 11px; border-top: 1px solid var(--border-color); }
		.kd-partyrow { display: grid; grid-template-columns: minmax(150px, 2.1fr) minmax(44px, 1fr) auto;
			gap: 14px; align-items: center; padding: 5px 0; font-size: 14px; }
		.kd-partynom { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
		.kd-partysum { font-variant-numeric: tabular-nums; text-align: right; white-space: nowrap; font-weight: 500; }

		/* --- murakkab --- */
		.kd-mrow { display: grid; grid-template-columns: 110px minmax(170px, auto) minmax(150px, 1fr) auto;
			gap: 16px; align-items: baseline; padding: 8px 0; font-size: 14px;
			border-bottom: 1px solid var(--border-color); }
		.kd-mrow:last-child { border-bottom: none; }
		.kd-msum { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }

		@media (max-width: 780px) {
			.kd-oqimrow { grid-template-columns: 1fr auto; }
			.kd-oqimbar, .kd-oqimpct { display: none; }
			.kd-mrow { grid-template-columns: 1fr; gap: 3px; }
			.kd-msum { text-align: left; }
		}
		`;
		$(`<style id="kd-styles">${css}</style>`).appendTo(document.head);
	}
}
