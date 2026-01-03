frappe.pages['trip-monitoring'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Trip Monitoring',
		single_column: true
	});

	// Render template
	page.main.html(frappe.render_template('trip_monitoring'));

	// Add styles
	addStyles();

	// Store dashboard on page for on_page_show
	page.tripDashboard = new TripMonitoringDashboard(page);
};

frappe.pages['trip-monitoring'].on_page_show = function (wrapper) {
	// Reload when navigating back
	if (wrapper && wrapper.page && wrapper.page.tripDashboard) {
		var trip_id = frappe.get_route()[1];
		if (trip_id && trip_id !== wrapper.page.tripDashboard.trip_id) {
			wrapper.page.tripDashboard.trip_id = trip_id;
			wrapper.page.tripDashboard.loadTripData();
		}
	}
};

class TripMonitoringDashboard {
	constructor(page) {
		this.page = page;
		this.wrapper = $(page.main);
		this.trip_id = this.getTripIdFromRoute();
		this.map = null;
		this.trip = null;

		this.init();
	}

	getTripIdFromRoute() {
		var route = frappe.get_route();
		return route.length > 1 ? route[1] : null;
	}

	init() {
		this.bindEvents();

		if (this.trip_id) {
			this.loadTripData();
		} else {
			this.showTripSelector();
		}
	}

	bindEvents() {
		var self = this;
		this.wrapper.find('.btn-refresh').on('click', function () {
			self.refreshData();
		});
		this.wrapper.find('.btn-back').on('click', function () {
			if (self.trip_id) {
				frappe.set_route('Form', 'Trip Master', self.trip_id);
			} else {
				frappe.set_route('List', 'Trip Master');
			}
		});
	}

	showTripSelector() {
		var self = this;
		this.wrapper.find('.trip-title').text('Trip tanlang');
		this.wrapper.find('.trip-meta').html('');

		frappe.call({
			method: 'frappe.client.get_list',
			args: {
				doctype: 'Trip Master',
				filters: { docstatus: 1 },
				fields: ['name', 'title', 'status', 'from_date', 'to_date', 'destination'],
				order_by: 'from_date desc',
				limit_page_length: 20
			},
			callback: function (r) {
				if (r.message && r.message.length) {
					self.renderTripList(r.message);
				} else {
					self.wrapper.find('.trip-map-container').html(
						'<div class="empty-state"><i class="fa fa-plane"></i><p>Hech qanday trip topilmadi</p></div>'
					);
				}
			}
		});
	}

	renderTripList(trips) {
		var self = this;
		var html = '';
		trips.forEach(function (trip) {
			html += '<div class="trip-list-item" data-trip="' + trip.name + '">';
			html += '<div class="trip-list-title">' + (trip.title || trip.name) + '</div>';
			html += '<div class="trip-list-meta">';
			html += '<span class="status-badge status-' + (trip.status || 'draft').toLowerCase() + '">' + trip.status + '</span> ';
			html += '<span>' + (trip.destination || '') + '</span> ';
			html += '<span>' + (trip.from_date || '') + ' - ' + (trip.to_date || '') + '</span>';
			html += '</div></div>';
		});

		this.wrapper.find('.trip-map-container').html(
			'<div class="trip-list-container"><h3>Active Triplar</h3>' + html + '</div>'
		);

		this.wrapper.find('.trip-list-item').on('click', function () {
			var trip_id = $(this).data('trip');
			frappe.set_route('trip-monitoring', trip_id);
		});
	}

	loadTripData() {
		var self = this;

		// Show loading in map area
		this.wrapper.find('.trip-map-container').html(
			'<div class="empty-state"><i class="fa fa-spinner fa-spin"></i><p>Yuklanmoqda...</p></div>'
		);

		frappe.call({
			method: 'frappe.client.get',
			args: { doctype: 'Trip Master', name: this.trip_id },
			callback: function (r) {
				if (r.message) {
					self.trip = r.message;
					self.renderHeader(r.message);
					self.loadBudgetData();
					self.renderMembers(r.message.members || []);
					self.loadPathData();
				} else {
					self.wrapper.find('.trip-map-container').html(
						'<div class="empty-state"><i class="fa fa-exclamation-triangle"></i><p>Trip topilmadi</p></div>'
					);
				}
			},
			error: function (err) {
				console.error('Trip load error:', err);
				self.wrapper.find('.trip-map-container').html(
					'<div class="empty-state"><i class="fa fa-exclamation-triangle"></i><p>Xatolik yuz berdi</p></div>'
				);
			}
		});
	}

	renderHeader(trip) {
		this.page.set_title(trip.title || trip.name);
		this.wrapper.find('.trip-title').text(trip.title || trip.name);

		var meta = '<span class="status-badge status-' + (trip.status || 'draft').toLowerCase() + '">' + trip.status + '</span> ';
		meta += '<span><i class="fa fa-map-marker"></i> ' + (trip.destination || 'N/A') + '</span> ';
		meta += '<span><i class="fa fa-calendar"></i> ' + (trip.from_date || '') + ' - ' + (trip.to_date || '') + '</span>';
		this.wrapper.find('.trip-meta').html(meta);
	}

	loadBudgetData() {
		var self = this;

		frappe.call({
			method: 'akfa_accounting.api.get_trip_balance',
			args: { trip_id: this.trip_id },
			callback: function (r) {
				if (r.message && r.message.success) {
					self.renderBudget(r.message);
				}
			},
			error: function (err) {
				console.error('Budget load error:', err);
			}
		});
	}

	renderBudget(data) {
		var currency = data.currency === 'UZS' ? "so'm" : data.currency;
		var percent = parseFloat(data.utilization_percent) || 0;
		var utilization_color = percent < 70 ? '#10b981' : (percent < 90 ? '#f59e0b' : '#ef4444');

		var html = '<div class="budget-item"><span class="budget-label">Umumiy byudjet</span>';
		html += '<span class="budget-value" style="color: #6366f1;">' + this.formatNumber(data.budget) + ' ' + currency + '</span></div>';
		html += '<div class="budget-item"><span class="budget-label">Sarflangan</span>';
		html += '<span class="budget-value" style="color: #ef4444;">' + this.formatNumber(data.spent) + ' ' + currency + '</span></div>';
		html += '<div class="budget-item"><span class="budget-label">Qoldiq</span>';
		html += '<span class="budget-value" style="color: #10b981;">' + this.formatNumber(data.balance) + ' ' + currency + '</span></div>';
		html += '<div class="budget-progress"><div class="progress-bar" style="width: ' + Math.min(percent, 100) + '%; background: ' + utilization_color + ';"></div></div>';
		html += '<div class="budget-percent" style="color: ' + utilization_color + ';">' + percent.toFixed(1) + '% ishlatilgan</div>';

		this.wrapper.find('.budget-content').html(html);
	}

	renderMembers(members) {
		if (!members.length) {
			this.wrapper.find('.members-content').html('<p class="text-muted">Azolar yoq</p>');
			return;
		}

		var html = '';
		members.forEach(function (m) {
			var initial = ((m.employee_name || m.employee || '?')[0] || '?').toUpperCase();
			html += '<div class="member-item">';
			html += '<div class="member-avatar">' + initial + '</div>';
			html += '<div class="member-info">';
			html += '<div class="member-name">' + (m.employee_name || m.employee) + '</div>';
			if (m.is_leader) html += '<span class="leader-badge">Rahbar</span>';
			html += '</div></div>';
		});

		this.wrapper.find('.members-content').html(html);
	}

	loadPathData() {
		var self = this;

		frappe.call({
			method: 'akfa_accounting.api.get_trip_path',
			args: { trip_master: this.trip_id },
			callback: function (r) {
				var points = (r.message || []).filter(function (p) {
					return p.latitude && p.longitude;
				});
				self.renderCheckins(points);
				self.renderMap(points);
			},
			error: function (err) {
				console.error('Path load error:', err);
				self.wrapper.find('.trip-map-container').html(
					'<div class="empty-state"><i class="fa fa-exclamation-triangle"></i><p>Path yuklanmadi</p></div>'
				);
			}
		});
	}

	renderCheckins(points) {
		if (!points.length) {
			this.wrapper.find('.checkins-content').html('<p class="text-muted">Check-inlar yoq</p>');
			return;
		}

		var recent = points.slice(-5).reverse();
		var html = '';
		var self = this;
		recent.forEach(function (p) {
			html += '<div class="checkin-item">';
			html += '<div class="checkin-icon"><i class="fa fa-map-pin"></i></div>';
			html += '<div class="checkin-info">';
			html += '<div class="checkin-name">' + (p.employee_name || 'Nomalum') + '</div>';
			html += '<div class="checkin-time">' + self.formatDatetime(p.timestamp) + '</div>';
			html += '</div></div>';
		});

		this.wrapper.find('.checkins-content').html(html);
	}

	renderMap(points) {
		var self = this;
		var container = this.wrapper.find('.trip-map-container');

		if (!points.length) {
			container.html('<div class="empty-state"><i class="fa fa-map-o"></i><p>Check-in malumotlari yoq</p></div>');
			return;
		}

		// Prepare map container with explicit ID and height
		container.html('<div id="trip-live-map" style="width: 100%; height: 100%; min-height: 400px;"></div>');

		// Load Leaflet and render map
		this.loadLeaflet(function () {
			// Small delay to ensure DOM is ready
			setTimeout(function () {
				self.initMap(points);
			}, 100);
		});
	}

	loadLeaflet(callback) {
		// Add CSS
		if (!document.getElementById('leaflet-css-link')) {
			var link = document.createElement('link');
			link.id = 'leaflet-css-link';
			link.rel = 'stylesheet';
			link.href = 'https://unpkg.com/[email protected]/dist/leaflet.css';
			document.head.appendChild(link);
		}

		// Load JS
		if (window.L) {
			callback();
		} else {
			var script = document.createElement('script');
			script.src = 'https://unpkg.com/[email protected]/dist/leaflet.js';
			script.onload = callback;
			document.head.appendChild(script);
		}
	}

	initMap(points) {
		var mapEl = document.getElementById('trip-live-map');
		if (!mapEl) {
			console.error('Map container not found');
			return;
		}

		// Cleanup old map
		if (this.map) {
			this.map.remove();
			this.map = null;
		}

		try {
			this.map = L.map('trip-live-map');

			L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
				attribution: '&copy; OpenStreetMap'
			}).addTo(this.map);

			var coords = points.map(function (p) {
				return [parseFloat(p.latitude), parseFloat(p.longitude)];
			});

			// Draw polyline
			var polyline = L.polyline(coords, {
				color: '#6366f1',
				weight: 4,
				opacity: 0.8
			}).addTo(this.map);

			// Add markers
			var colors = ['#ef4444', '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899'];
			var employeeColors = {};
			var colorIdx = 0;
			var self = this;

			points.forEach(function (point, idx) {
				var empName = point.employee_name || 'Unknown';
				if (!employeeColors[empName]) {
					employeeColors[empName] = colors[colorIdx % colors.length];
					colorIdx++;
				}

				var isLast = idx === points.length - 1;
				var marker = L.circleMarker(
					[parseFloat(point.latitude), parseFloat(point.longitude)],
					{
						radius: isLast ? 10 : 6,
						color: employeeColors[empName],
						fillColor: employeeColors[empName],
						fillOpacity: isLast ? 1 : 0.7,
						weight: isLast ? 3 : 1
					}
				).addTo(self.map);

				marker.bindPopup('<strong>' + empName + '</strong><br>' + self.formatDatetime(point.timestamp));

				if (isLast) {
					marker.openPopup();
				}
			});

			// Fit bounds
			this.map.fitBounds(polyline.getBounds(), { padding: [30, 30] });
		} catch (err) {
			console.error('Map init error:', err);
		}
	}

	refreshData() {
		var self = this;
		frappe.show_alert({ message: 'Yangilanmoqda...', indicator: 'blue' });
		this.loadBudgetData();
		this.loadPathData();
	}

	formatNumber(num) {
		return new Intl.NumberFormat('uz-UZ').format(num || 0);
	}

	formatDatetime(dt) {
		if (!dt) return '';
		try {
			return frappe.datetime.str_to_user(dt);
		} catch (e) {
			return dt;
		}
	}
}

function addStyles() {
	if (document.getElementById('trip-monitoring-styles')) return;

	var css = '';
	css += '.trip-monitoring-container { min-height: calc(100vh - 120px); display: flex; flex-direction: column; }';
	css += '.trip-monitoring-header { display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 12px; margin: 10px; flex-wrap: wrap; gap: 10px; }';
	css += '.trip-title { margin: 0; font-size: 20px; font-weight: 600; }';
	css += '.trip-meta { display: flex; gap: 16px; margin-top: 8px; font-size: 14px; opacity: 0.9; flex-wrap: wrap; }';
	css += '.trip-meta i { margin-right: 4px; }';
	css += '.trip-actions { display: flex; gap: 10px; }';
	css += '.trip-actions .btn { background: rgba(255,255,255,0.2); color: white; border: none; }';
	css += '.trip-actions .btn:hover { background: rgba(255,255,255,0.3); }';
	css += '.trip-monitoring-body { flex: 1; display: flex; gap: 16px; padding: 0 10px 10px; min-height: 0; flex-wrap: wrap; }';
	css += '.trip-sidebar { width: 320px; min-width: 280px; display: flex; flex-direction: column; gap: 12px; }';
	css += '.sidebar-card { background: white; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); overflow: hidden; }';
	css += '.card-header { padding: 12px 16px; background: #f8fafc; font-weight: 600; font-size: 14px; color: #334155; border-bottom: 1px solid #e2e8f0; }';
	css += '.card-header i { margin-right: 8px; color: #6366f1; }';
	css += '.card-body { padding: 16px; }';
	// Budget
	css += '.budget-item { display: flex; justify-content: space-between; margin-bottom: 8px; flex-wrap: wrap; }';
	css += '.budget-label { color: #64748b; font-size: 13px; }';
	css += '.budget-value { font-weight: 600; font-size: 14px; }';
	css += '.budget-progress { height: 8px; background: #e2e8f0; border-radius: 4px; overflow: hidden; margin: 12px 0 8px; }';
	css += '.progress-bar { height: 100%; border-radius: 4px; transition: width 0.3s ease; }';
	css += '.budget-percent { text-align: right; font-size: 12px; font-weight: 600; }';
	// Members
	css += '.member-item { display: flex; align-items: center; gap: 12px; padding: 8px 0; border-bottom: 1px solid #f1f5f9; }';
	css += '.member-item:last-child { border-bottom: none; }';
	css += '.member-avatar { width: 36px; height: 36px; border-radius: 50%; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; display: flex; align-items: center; justify-content: center; font-weight: 600; font-size: 14px; flex-shrink: 0; }';
	css += '.member-name { font-weight: 500; font-size: 14px; }';
	css += '.leader-badge { background: #fef3c7; color: #d97706; font-size: 11px; padding: 2px 8px; border-radius: 10px; font-weight: 500; }';
	// Checkins
	css += '.checkin-item { display: flex; align-items: center; gap: 12px; padding: 8px 0; border-bottom: 1px solid #f1f5f9; }';
	css += '.checkin-item:last-child { border-bottom: none; }';
	css += '.checkin-icon { width: 32px; height: 32px; border-radius: 50%; background: #fef2f2; color: #ef4444; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }';
	css += '.checkin-name { font-weight: 500; font-size: 13px; }';
	css += '.checkin-time { font-size: 12px; color: #64748b; }';
	// Map
	css += '.trip-map-container { flex: 1; background: white; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); overflow: hidden; min-height: 400px; min-width: 300px; }';
	css += '#trip-live-map { height: 100%; width: 100%; min-height: 400px; }';
	css += '.empty-state { height: 100%; min-height: 400px; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #94a3b8; }';
	css += '.empty-state i { font-size: 48px; margin-bottom: 16px; }';
	// Status
	css += '.status-badge { padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 500; display: inline-block; }';
	css += '.status-active { background: rgba(59, 130, 246, 0.2); color: #3b82f6; }';
	css += '.status-completed { background: rgba(16, 185, 129, 0.2); color: #10b981; }';
	css += '.status-draft { background: rgba(100, 116, 139, 0.2); color: #64748b; }';
	// Trip list
	css += '.trip-list-container { padding: 20px; }';
	css += '.trip-list-container h3 { margin-bottom: 16px; color: #334155; }';
	css += '.trip-list-item { padding: 16px; background: #f8fafc; border-radius: 10px; margin-bottom: 10px; cursor: pointer; transition: all 0.2s ease; }';
	css += '.trip-list-item:hover { background: #e2e8f0; transform: translateX(4px); }';
	css += '.trip-list-title { font-weight: 600; font-size: 15px; margin-bottom: 8px; }';
	css += '.trip-list-meta { display: flex; gap: 12px; font-size: 13px; color: #64748b; flex-wrap: wrap; }';
	// Responsive
	css += '@media (max-width: 900px) { .trip-monitoring-body { flex-direction: column; } .trip-sidebar { width: 100%; flex-direction: row; overflow-x: auto; } .sidebar-card { min-width: 250px; flex: 1; } }';
	css += '@media (max-width: 600px) { .trip-sidebar { flex-direction: column; } .sidebar-card { min-width: 100%; } .trip-meta { flex-direction: column; gap: 5px; } }';

	var style = document.createElement('style');
	style.id = 'trip-monitoring-styles';
	style.innerHTML = css;
	document.head.appendChild(style);
}
