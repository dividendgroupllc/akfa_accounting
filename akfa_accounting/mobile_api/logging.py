import frappe
from frappe import _
from frappe.utils import now_datetime


def log_trip_path(trip_master, employee, latitude, longitude, activity_type=None):
	user = _validate_session_user()
	session_employee = _get_employee_for_user(user)
	_enforce_employee_scope(employee, session_employee)

	trip = _load_active_trip(trip_master)
	_ensure_membership(trip, employee)

	geojson = _build_geojson(latitude, longitude)
	log = _create_trip_log(trip_master, employee, geojson, latitude, longitude, activity_type)
	return _success_payload(log)


def _validate_session_user():
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Authentication required"), frappe.PermissionError)
	return user


def _get_employee_for_user(user):
	employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if not employee:
		frappe.throw(_("No employee linked to user {0}").format(user), frappe.PermissionError)
	return employee


def _enforce_employee_scope(requested_employee, session_employee):
	if requested_employee != session_employee:
		frappe.local.response["http_status_code"] = 403
		frappe.throw(
			_("Forbidden: You can only log location for your own employee account"),
			frappe.PermissionError,
		)


def _load_active_trip(trip_master):
	trip = frappe.get_doc("Trip Master", trip_master)
	if trip.docstatus != 1:
		frappe.throw(_("Trip Master {0} is not submitted").format(trip_master))
	if trip.status != "Active":
		frappe.throw(_("Trip Master {0} is not active").format(trip_master))
	return trip


def _ensure_membership(trip, employee):
	if any(member.employee == employee for member in trip.members):
		return
	frappe.local.response["http_status_code"] = 403
	frappe.throw(
		_("Forbidden: Employee {0} is not a member of Trip {1}").format(employee, trip.name),
		frappe.PermissionError,
	)


def _build_geojson(latitude, longitude):
	return {
		"type": "FeatureCollection",
		"features": [
			{
				"type": "Feature",
				"properties": {},
				"geometry": {
					"type": "Point",
					"coordinates": [float(longitude), float(latitude)],
				},
			}
		],
	}


def _create_trip_log(trip_master, employee, location, latitude, longitude, activity_type):
	log = frappe.new_doc("Trip Path Log")
	log.trip_master = trip_master
	log.employee = employee
	log.timestamp = now_datetime()
	log.location = frappe.as_json(location)
	log.latitude = float(latitude)
	log.longitude = float(longitude)

	if activity_type:
		log.activity_type = activity_type

	log.flags.ignore_permissions = True
	log.insert()
	frappe.db.commit()
	return log


def _success_payload(log):
	return {
		"success": True,
		"message": _("Location logged successfully"),
		"log_id": log.name,
	}
