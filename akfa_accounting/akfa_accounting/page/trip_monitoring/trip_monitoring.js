frappe.pages['trip-monitoring'].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Trip Monitoring',
		single_column: true
	});

	page.main.html(frappe.render_template('trip_monitoring'));
	add_styles();

	page.dashboard = new TripMonitoringDashboard(page);
};

frappe.pages['trip-monitoring'].on_page_show = function (wrapper) {
	// Reload data when navigating back to this page
	if (wrapper && wrapper.page && wrapper.page.dashboard) {
		const trip_id = frappe.get_route()[1];
		if (trip_id && trip_id !== wrapper.page.dashboard.trip_id) {
			wrapper.page.dashboard.trip_id = trip_id;
			wrapper.page.dashboard.load_trip_data();
		}
	}
};

class TripMonitoringDashboard {
	constructor(page) {
		this.page = page;
		this.wrapper = page.main;
		this.trip_id = this.get_trip_id_from_route();
		this.map = null;
		this.markers = [];
		this.polyline = null;
		this.auto_refresh_interval = null;

		this.init();
	}

	get_trip_id_from_route() {
		const route = frappe.get_route();
		return route.length > 1 ? route[1] : null;
	}

	async init() {
		this.bind_events();

		if (this.trip_id) {
			await this.load_trip_data();
			this.start_auto_refresh();
		} else {
			this.show_trip_selector();
		}
	}

	bind_events() {
		this.wrapper.find('.btn-refresh').on('click', () => this.refresh_data());
		this.wrapper.find('.btn-back').on('click', () => {
			if (this.trip_id) {
				frappe.set_route('Form', 'Trip Master', this.trip_id);
			} else {
				frappe.set_route('List', 'Trip Master');
			}
		});
	}

	show_trip_selector() {
		this.wrapper.find('.trip-title').text('Trip tanlang');
		this.wrapper.find('.trip-meta').html('');

		// Load active trips
		frappe.call({
			method: 'frappe.client.get_list',
			args: {
				doctype: 'Trip Master',
				filters: { docstatus: 1 },
				fields: ['name', 'title', 'status', 'from_date', 'to_date', 'destination'],
				order_by: 'from_date desc',
				limit_page_length: 20
			},
			callback: (r) => {
				if (r.message && r.message.length) {
					this.render_trip_list(r.message);
				} else {
					this.wrapper.find('.trip-map-container').html(
						'<div class="empty-state"><i class="fa fa-plane"></i><p>Hech qanday trip topilmadi</p></div>'
					);
				}
			}
		});
	}

	render_trip_list(trips) {
		const html = trips.map(trip => `
			<div class="trip-list-item" data-trip="${trip.name}">
				<div class="trip-list-title">${trip.title || trip.name}</div>
				<div class="trip-list-meta">
					<span class="status-badge status-${trip.status.toLowerCase()}">${trip.status}</span>
					<span>${trip.destination || ''}</span>
					<span>${frappe.datetime.str_to_user(trip.from_date)} - ${frappe.datetime.str_to_user(trip.to_date)}</span>
				</div>
			</div>
		`).join('');

		this.wrapper.find('.trip-map-container').html(`
			<div class="trip-list-container">
				<h3>Active Triplar</h3>
				${html}
			</div>
		`);

		this.wrapper.find('.trip-list-item').on('click', (e) => {
			const trip_id = $(e.currentTarget).data('trip');
			frappe.set_route('trip-monitoring', trip_id);
		});
	}

	async load_trip_data() {
		frappe.show_progress('Yuklanmoqda...', 30, 100);

		try {
			// Load trip details
			const trip = await frappe.db.get_doc('Trip Master', this.trip_id);
			this.trip = trip;
			this.render_header(trip);

			frappe.show_progress('Yuklanmoqda...', 50, 100);

			// Load budget data
			await this.load_budget_data();

			frappe.show_progress('Yuklanmoqda...', 70, 100);

			// Load path data
			await this.load_path_data();

			// Render members
			this.render_members(trip.members || []);

			frappe.hide_progress();
		} catch (err) {
			frappe.hide_progress();
			frappe.msgprint({
				title: __('Xatolik'),
				message: err.message || 'Trip yuklanmadi',
				indicator: 'red'
			});
		}
	}

	render_header(trip) {
		this.page.set_title(`${trip.title || trip.name}`);
		this.wrapper.find('.trip-title').text(trip.title || trip.name);
		this.wrapper.find('.trip-meta').html(`
			<span class="status-badge status-${trip.status.toLowerCase()}">${trip.status}</span>
			<span><i class="fa fa-map-marker"></i> ${trip.destination || 'N/A'}</span>
			<span><i class="fa fa-calendar"></i> ${frappe.datetime.str_to_user(trip.from_date)} - ${frappe.datetime.str_to_user(trip.to_date)}</span>
		`);
	}

	async load_budget_data() {
		try {
			const r = await frappe.call({
				method: 'akfa_accounting.api.get_trip_balance',
				args: { trip_id: this.trip_id }
			});

			if (r.message && r.message.success) {
				this.render_budget(r.message);
			}
		} catch (err) {
			console.error('Budget load error:', err);
		}
	}

	render_budget(data) {
		const currency = data.currency === 'UZS' ? "so'm" : data.currency;
		const utilization_color = data.utilization_percent < 70 ? '#10b981' :
			data.utilization_percent < 90 ? '#f59e0b' : '#ef4444';

		this.wrapper.find('.budget-content').html(`
			<div class="budget-item budget-total">
				<div class="budget-label">Umumiy byudjet</div>
				<div class="budget-value">${this.format_number(data.budget)} ${currency}</div>
			</div>
			<div class="budget-item budget-spent">
				<div class="budget-label">Sarflangan</div>
				<div class="budget-value">${this.format_number(data.spent)} ${currency}</div>
			</div>
			<div class="budget-item budget-balance">
				<div class="budget-label">Qoldiq</div>
				<div class="budget-value">${this.format_number(data.balance)} ${currency}</div>
			</div>
			<div class="budget-progress">
				<div class="progress-bar" style="width: ${Math.min(data.utilization_percent, 100)}%; background: ${utilization_color};"></div>
			</div>
			<div class="budget-percent" style="color: ${utilization_color};">${data.utilization_percent}% ishlatilgan</div>
		`);
	}

	render_members(members) {
		if (!members.length) {
			this.wrapper.find('.members-content').html('<p class="text-muted">Azolar yoq</p>');
			return;
		}

		const html = members.map(m => `
			<div class="member-item">
				<div class="member-avatar">${(m.employee_name || m.employee || '?')[0].toUpperCase()}</div>
				<div class="member-info">
					<div class="member-name">${m.employee_name || m.employee}</div>
					${m.is_leader ? '<span class="leader-badge">Rahbar</span>' : ''}
				</div>
			</div>
		`).join('');

		this.wrapper.find('.members-content').html(html);
	}

	async load_path_data() {
		try {
			const r = await frappe.call({
				method: 'akfa_accounting.api.get_trip_path',
				args: { trip_master: this.trip_id }
			});

			const points = (r.message || []).filter(p => p.latitude && p.longitude);
			this.render_checkins(points);
			this.render_map(points);
		} catch (err) {
			console.error('Path load error:', err);
		}
	}

	render_checkins(points) {
		if (!points.length) {
			this.wrapper.find('.checkins-content').html('<p class="text-muted">Check-inlar yoq</p>');
			return;
		}

		// Show last 5 checkins
		const recent = points.slice(-5).reverse();
		const html = recent.map(p => `
			<div class="checkin-item">
				<div class="checkin-icon"><i class="fa fa-map-pin"></i></div>
				<div class="checkin-info">
					<div class="checkin-name">${p.employee_name || 'Nomalum'}</div>
					<div class="checkin-time">${this.format_datetime(p.timestamp)}</div>
				</div>
			</div>
		`).join('');

		this.wrapper.find('.checkins-content').html(html);
	}

	render_map(points) {
		const container = this.wrapper.find('#trip-live-map');

		if (!points.length) {
			container.html('<div class="empty-map"><i class="fa fa-map-o"></i><p>Check-in malumotlari yoq</p></div>');
			return;
		}

		// Ensure Leaflet is loaded
		this.ensure_leaflet(() => {
			if (this.map) {
				this.map.remove();
			}

			this.map = L.map('trip-live-map');
			L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
				attribution: '&copy; OpenStreetMap contributors'
			}).addTo(this.map);

			const coords = points.map(p => [parseFloat(p.latitude), parseFloat(p.longitude)]);

			// Draw polyline
			this.polyline = L.polyline(coords, {
				color: '#6366f1',
				weight: 4,
				opacity: 0.8
			}).addTo(this.map);

			// Add markers with employee colors
			const employee_colors = {};
			const colors = ['#ef4444', '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899'];
			let color_idx = 0;

			points.forEach((point, idx) => {
				const emp_name = point.employee_name || 'Unknown';
				if (!employee_colors[emp_name]) {
					employee_colors[emp_name] = colors[color_idx % colors.length];
					color_idx++;
				}

				const is_last = idx === points.length - 1;
				const marker = L.circleMarker(
					[parseFloat(point.latitude), parseFloat(point.longitude)],
					{
						radius: is_last ? 10 : 6,
						color: employee_colors[emp_name],
						fillColor: employee_colors[emp_name],
						fillOpacity: is_last ? 1 : 0.7,
						weight: is_last ? 3 : 1
					}
				).addTo(this.map);

				marker.bindPopup(`
					<strong>${emp_name}</strong><br>
					${this.format_datetime(point.timestamp)}<br>
					${point.activity_type || ''}
				`);

				if (is_last) {
					marker.openPopup();
				}
			});

			// Fit bounds
			this.map.fitBounds(this.polyline.getBounds(), { padding: [30, 30] });
		});
	}

	ensure_leaflet(callback) {
		// Add CSS
		if (!document.getElementById('leaflet-css')) {
			const link = document.createElement('link');
			link.id = 'leaflet-css';
			link.rel = 'stylesheet';
			link.href = '/assets/frappe/css/leaflet.css';
			document.head.appendChild(link);
		}

		// Load JS
		if (window.L) {
			callback();
		} else {
			frappe.require('assets/frappe/js/lib/leaflet/leaflet.js', callback);
		}
	}

	async refresh_data() {
		frappe.show_alert({ message: 'Yangilanmoqda...', indicator: 'blue' });
		await this.load_path_data();
		await this.load_budget_data();
		frappe.show_alert({ message: 'Yangilandi!', indicator: 'green' });
	}

	start_auto_refresh() {
		// Refresh every 60 seconds
		this.auto_refresh_interval = setInterval(() => {
			this.load_path_data();
		}, 60000);
	}

	format_number(num) {
		return new Intl.NumberFormat('uz-UZ').format(num || 0);
	}

	format_datetime(dt) {
		if (!dt) return '';
		return frappe.datetime.str_to_user(dt);
	}
}

function add_styles() {
	if (document.getElementById('trip-monitoring-styles')) return;

	const style = document.createElement('style');
	style.id = 'trip-monitoring-styles';
	style.innerHTML = `
		.trip-monitoring-container {
			height: calc(100vh - 120px);
			display: flex;
			flex-direction: column;
		}

		.trip-monitoring-header {
			display: flex;
			justify-content: space-between;
			align-items: center;
			padding: 16px 20px;
			background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
			color: white;
			border-radius: 12px;
			margin: 10px;
		}

		.trip-title {
			margin: 0;
			font-size: 22px;
			font-weight: 600;
		}

		.trip-meta {
			display: flex;
			gap: 16px;
			margin-top: 8px;
			font-size: 14px;
			opacity: 0.9;
		}

		.trip-meta i {
			margin-right: 4px;
		}

		.trip-actions {
			display: flex;
			gap: 10px;
		}

		.trip-actions .btn {
			background: rgba(255,255,255,0.2);
			color: white;
			border: none;
		}

		.trip-actions .btn:hover {
			background: rgba(255,255,255,0.3);
		}

		.trip-monitoring-body {
			flex: 1;
			display: flex;
			gap: 16px;
			padding: 0 10px 10px;
			min-height: 0;
		}

		.trip-sidebar {
			width: 320px;
			display: flex;
			flex-direction: column;
			gap: 12px;
			overflow-y: auto;
		}

		.sidebar-card {
			background: white;
			border-radius: 12px;
			box-shadow: 0 2px 8px rgba(0,0,0,0.08);
			overflow: hidden;
		}

		.card-header {
			padding: 12px 16px;
			background: #f8fafc;
			font-weight: 600;
			font-size: 14px;
			color: #334155;
			border-bottom: 1px solid #e2e8f0;
		}

		.card-header i {
			margin-right: 8px;
			color: #6366f1;
		}

		.card-body {
			padding: 16px;
		}

		/* Budget styles */
		.budget-item {
			display: flex;
			justify-content: space-between;
			margin-bottom: 10px;
		}

		.budget-label {
			color: #64748b;
			font-size: 13px;
		}

		.budget-value {
			font-weight: 600;
			font-size: 14px;
		}

		.budget-total .budget-value {
			color: #6366f1;
		}

		.budget-spent .budget-value {
			color: #ef4444;
		}

		.budget-balance .budget-value {
			color: #10b981;
		}

		.budget-progress {
			height: 8px;
			background: #e2e8f0;
			border-radius: 4px;
			overflow: hidden;
			margin: 12px 0 8px;
		}

		.progress-bar {
			height: 100%;
			border-radius: 4px;
			transition: width 0.3s ease;
		}

		.budget-percent {
			text-align: right;
			font-size: 12px;
			font-weight: 600;
		}

		/* Members styles */
		.member-item {
			display: flex;
			align-items: center;
			gap: 12px;
			padding: 8px 0;
			border-bottom: 1px solid #f1f5f9;
		}

		.member-item:last-child {
			border-bottom: none;
		}

		.member-avatar {
			width: 36px;
			height: 36px;
			border-radius: 50%;
			background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
			color: white;
			display: flex;
			align-items: center;
			justify-content: center;
			font-weight: 600;
			font-size: 14px;
		}

		.member-name {
			font-weight: 500;
			font-size: 14px;
		}

		.leader-badge {
			background: #fef3c7;
			color: #d97706;
			font-size: 11px;
			padding: 2px 8px;
			border-radius: 10px;
			font-weight: 500;
		}

		/* Checkin styles */
		.checkin-item {
			display: flex;
			align-items: center;
			gap: 12px;
			padding: 8px 0;
			border-bottom: 1px solid #f1f5f9;
		}

		.checkin-item:last-child {
			border-bottom: none;
		}

		.checkin-icon {
			width: 32px;
			height: 32px;
			border-radius: 50%;
			background: #fef2f2;
			color: #ef4444;
			display: flex;
			align-items: center;
			justify-content: center;
		}

		.checkin-name {
			font-weight: 500;
			font-size: 13px;
		}

		.checkin-time {
			font-size: 12px;
			color: #64748b;
		}

		/* Map container */
		.trip-map-container {
			flex: 1;
			background: white;
			border-radius: 12px;
			box-shadow: 0 2px 8px rgba(0,0,0,0.08);
			overflow: hidden;
			min-height: 400px;
		}

		#trip-live-map {
			height: 100%;
			width: 100%;
		}

		.empty-map, .empty-state {
			height: 100%;
			display: flex;
			flex-direction: column;
			align-items: center;
			justify-content: center;
			color: #94a3b8;
		}

		.empty-map i, .empty-state i {
			font-size: 48px;
			margin-bottom: 16px;
		}

		/* Status badges */
		.status-badge {
			padding: 4px 12px;
			border-radius: 20px;
			font-size: 12px;
			font-weight: 500;
		}

		.status-active {
			background: rgba(59, 130, 246, 0.2);
			color: #3b82f6;
		}

		.status-completed {
			background: rgba(16, 185, 129, 0.2);
			color: #10b981;
		}

		.status-draft {
			background: rgba(100, 116, 139, 0.2);
			color: #64748b;
		}

		.status-cancelled {
			background: rgba(239, 68, 68, 0.2);
			color: #ef4444;
		}

		/* Trip list */
		.trip-list-container {
			padding: 20px;
		}

		.trip-list-container h3 {
			margin-bottom: 16px;
			color: #334155;
		}

		.trip-list-item {
			padding: 16px;
			background: #f8fafc;
			border-radius: 10px;
			margin-bottom: 10px;
			cursor: pointer;
			transition: all 0.2s ease;
		}

		.trip-list-item:hover {
			background: #e2e8f0;
			transform: translateX(4px);
		}

		.trip-list-title {
			font-weight: 600;
			font-size: 15px;
			margin-bottom: 8px;
		}

		.trip-list-meta {
			display: flex;
			gap: 12px;
			font-size: 13px;
			color: #64748b;
		}

		/* Responsive */
		@media (max-width: 768px) {
			.trip-monitoring-body {
				flex-direction: column;
			}

			.trip-sidebar {
				width: 100%;
				flex-direction: row;
				flex-wrap: wrap;
			}

			.sidebar-card {
				flex: 1;
				min-width: 280px;
			}

			.trip-map-container {
				min-height: 300px;
			}
		}
	`;
	document.head.appendChild(style);
}
