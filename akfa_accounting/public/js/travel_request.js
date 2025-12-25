frappe.ui.form.on('Travel Request', {
	refresh(frm) {
		render_itinerary_ui(frm);
	}
});

function render_itinerary_ui(frm) {
	ensure_styles();
	const trip_master = frm.doc.custom_trip_master;

	fetch_trip_itinerary(trip_master).then((meta) => {
		const itinerary = get_itinerary_data(frm, meta);
		if (!itinerary.length && !meta) {
			return;
		}

		const shell = ensure_shell(frm);
		shell.html(build_itinerary_section(itinerary, meta));
		bind_toggle(shell);
		bind_checkin(shell, frm);
	});
}

function fetch_trip_itinerary(trip_master) {
	if (!trip_master) {
		return Promise.resolve(null);
	}

	return new Promise((resolve) => {
		frappe.call({
			method: 'akfa_accounting.api.get_trip_itinerary',
			args: { trip_master },
			callback: (r) => resolve(r.message || null),
			error: () => resolve(null)
		});
	});
}

function get_itinerary_data(frm, meta) {
	if (meta && Array.isArray(meta.itinerary) && meta.itinerary.length) {
		return meta.itinerary;
	}

	if (Array.isArray(frm.doc.itinerary) && frm.doc.itinerary.length) {
		return frm.doc.itinerary;
	}

	return [];
}

function ensure_shell(frm) {
	const wrapper = frm.fields_dict.custom_trip_summary_html?.$wrapper
		|| frm.fields_dict.custom_trip_master?.$wrapper
		|| frm.fields_dict.itinerary?.$wrapper;
	const existing = wrapper?.parent().find('.akfa-itinerary-shell');

	if (existing && existing.length) {
		return existing;
	}

	const shell = $('<div class="form-section akfa-itinerary-shell"></div>');
	if (wrapper?.length) {
		wrapper.before(shell);
	} else {
		frm.layout.wrapper.prepend(shell);
	}
	return shell;
}

function build_itinerary_section(itinerary, meta) {
	const route = build_route_string(itinerary);
	const days = calculate_trip_days(itinerary, meta);
	const timeline = build_timeline(itinerary);
	const date_range = build_date_range(meta);

	return `
		<div class="akfa-card">
			<div class="akfa-card-head">
				<div class="akfa-title">✈️ Travel Itinerary</div>
				<div class="akfa-pill">${days} Day${days !== 1 ? 's' : ''}</div>
			</div>
			${date_range ? `<div class="akfa-dates">${date_range}</div>` : ''}
			<div class="akfa-route">${route}</div>
			<button class="btn btn-xs akfa-toggle">📋 View Details</button>
		</div>
		<div class="akfa-details" style="display:none;">${timeline}</div>
		<div class="akfa-checkin-bar">
			<button class="btn btn-primary akfa-checkin">📍 Check-in</button>
			<span class="text-muted akfa-checkin-hint">Joylashuvni hozir log qilish uchun bosing.</span>
		</div>
	`;
}

function build_route_string(itinerary) {
	return itinerary.map((stop) => build_leg_label(stop)).join(' → ');
}

function build_leg_label(stop) {
	const from_city = stop.from_city || stop.travel_from || stop.destination;
	const to_city = stop.to_city || stop.travel_to;

	if (from_city && to_city) {
		return `${from_city} → ${to_city}`;
	}
	return from_city || to_city || 'N/A';
}

function calculate_trip_days(itinerary, meta) {
	if (!itinerary.length) {
		return meta ? calculate_days_from_dates(meta) : 0;
	}

	const first = itinerary[0];
	const last = itinerary[itinerary.length - 1];

	if (first.departure_datetime && last.arrival_datetime) {
		const start = frappe.datetime.str_to_obj(first.departure_datetime);
		const end = frappe.datetime.str_to_obj(last.arrival_datetime);
		return frappe.datetime.get_day_diff(end, start) + 1;
	}

	return meta ? calculate_days_from_dates(meta) : 0;
}

function calculate_days_from_dates(meta) {
	if (!meta?.from_date || !meta?.to_date) {
		return 0;
	}
	const start = frappe.datetime.str_to_obj(meta.from_date);
	const end = frappe.datetime.str_to_obj(meta.to_date);
	return frappe.datetime.get_day_diff(end, start) + 1;
}

function build_date_range(meta) {
	if (!meta?.from_date || !meta?.to_date) {
		return '';
	}
	const from_date = frappe.datetime.str_to_user(meta.from_date);
	const to_date = frappe.datetime.str_to_user(meta.to_date);
	return `${from_date} → ${to_date}`;
}

function build_timeline(itinerary) {
	return itinerary.map((stop, idx) => render_stop(stop, idx, itinerary.length)).join('');
}

function render_stop(stop, idx, total) {
	const departure = stop.departure_datetime
		? frappe.datetime.str_to_user(stop.departure_datetime)
		: 'N/A';
	const arrival = stop.arrival_datetime
		? frappe.datetime.str_to_user(stop.arrival_datetime)
		: 'N/A';
	const icon = idx === 0 ? '🚀' : (idx === total - 1 ? '🏁' : '📍');

	return `
		<div class="akfa-stop">
			<div class="akfa-stop-icon">${icon}</div>
			<div class="akfa-stop-body">
				<div class="akfa-stop-title">${build_leg_label(stop) || 'Unknown Destination'}</div>
				<div class="akfa-stop-meta">
					<div><span>Departure:</span><strong>${departure}</strong></div>
					<div><span>Arrival:</span><strong>${arrival}</strong></div>
				</div>
			</div>
		</div>
	`;
}

function bind_toggle(shell) {
	const toggle = shell.find('.akfa-toggle');
	const details = shell.find('.akfa-details');

	toggle.off('click').on('click', () => {
		const is_open = details.is(':visible');
		details.toggle(!is_open);
		toggle.text(is_open ? '📋 View Details' : '🔼 Hide Details');
	});
}

function bind_checkin(shell, frm) {
	const btn = shell.find('.akfa-checkin');
	btn.off('click').on('click', () => request_checkin(frm));
}

function request_checkin(frm) {
	const trip = frm.doc.custom_trip_master;
	const employee = frm.doc.employee;

	if (!trip || !employee) {
		frappe.msgprint(__('Trip Master va Employee talab qilinadi'));
		return;
	}

	if (!navigator.geolocation) {
		frappe.msgprint(__('Geolokatsiya brauzerda mavjud emas'));
		return;
	}

	navigator.geolocation.getCurrentPosition(
		position => submit_checkin(trip, employee, position.coords),
		error => frappe.msgprint(__('GPS xatolik: {0}', [error.message])),
		{ enableHighAccuracy: true, timeout: 15000 }
	);
}

function submit_checkin(trip_master, employee, coords) {
	const { latitude, longitude } = coords;

	frappe.call({
		method: 'akfa_accounting.api.log_trip_path',
		args: { trip_master, employee, latitude, longitude },
		freeze: true,
		freeze_message: __('Joylashuv jo\'natilmoqda...'),
		callback: (r) => {
			if (r.message?.success) {
				frappe.show_alert({
					message: __('Joylashuv log qilindi'),
					indicator: 'green'
				});
				return;
			}
			frappe.msgprint(__('Log qilish muvaffaqiyatsiz'));
		}
	});
}

function ensure_styles() {
	if (document.getElementById('akfa-itinerary-style')) {
		return;
	}

	const style = document.createElement('style');
	style.id = 'akfa-itinerary-style';
	style.innerHTML = ".akfa-card{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:#fff;padding:20px;border-radius:14px;margin:16px 0 8px 0;box-shadow:0 10px 24px rgba(118,75,162,0.25);}\
.akfa-card-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;}\
.akfa-title{font-size:18px;font-weight:600;}\
.akfa-pill{background:rgba(255,255,255,0.18);padding:6px 12px;border-radius:12px;font-size:12px;}\
.akfa-route{background:rgba(255,255,255,0.16);padding:12px 14px;border-radius:10px;margin-bottom:12px;font-weight:600;}\
.akfa-dates{font-size:12px;opacity:0.9;margin-bottom:8px;}\
.akfa-toggle{background:rgba(255,255,255,0.22);color:#fff;border:none;border-radius:12px;}\
.akfa-details{border:1px solid #667eea;border-radius:12px;padding:14px;margin-bottom:10px;background:#fff;box-shadow:0 6px 12px rgba(0,0,0,0.06);}\
.akfa-stop{display:flex;gap:12px;padding:10px 0;border-bottom:1px solid #eee;}\
.akfa-stop:last-child{border-bottom:none;}\
.akfa-stop-icon{font-size:22px;}\
.akfa-stop-body{flex:1;}\
.akfa-stop-title{font-weight:600;font-size:15px;color:#1a1a1a;margin-bottom:4px;}\
.akfa-stop-meta{display:flex;gap:16px;font-size:12px;color:#666;}\
.akfa-stop-meta span{color:#999;margin-right:4px;}\
.akfa-checkin-bar{display:flex;align-items:center;gap:10px;margin-bottom:6px;}\
.akfa-checkin-hint{font-size:12px;}";
	document.head.appendChild(style);
}
