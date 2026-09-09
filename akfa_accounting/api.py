import frappe

from akfa_accounting.mobile_api.expense_claim import create_expense_claim_mobile as create_expense_claim_mobile_service
from akfa_accounting.mobile_api.logging import log_trip_path as log_trip_path_service
from akfa_accounting.mobile_api.trip_info import (
	get_active_trip as get_active_trip_service,
	get_trip_balance as get_trip_balance_service,
)
 

def _check_trip_read(trip_master):
	"""Raise unless the current user may read this Trip Master."""
	if not frappe.has_permission("Trip Master", "read", trip_master):
		frappe.throw("Not permitted", frappe.PermissionError)


@frappe.whitelist()
def log_trip_path(trip_master, employee, latitude, longitude, activity_type=None):
	"""Whitelisted wrapper for mobile location logging."""
	return log_trip_path_service(trip_master, employee, latitude, longitude, activity_type)


@frappe.whitelist()
def get_active_trip(employee=None):
	"""Whitelisted wrapper to fetch active trip for an employee.

	Defaults to the session's own employee; querying somebody else needs HR rights.
	"""
	if employee:
		session_employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
		if employee != session_employee and not frappe.has_permission("Employee", "read", employee):
			frappe.throw("Not permitted", frappe.PermissionError)
	return get_active_trip_service(employee)


@frappe.whitelist()
def get_trip_balance(trip_id):
	"""Whitelisted wrapper to fetch trip budget balance."""
	_check_trip_read(trip_id)
	return get_trip_balance_service(trip_id)


@frappe.whitelist()
def get_trip_path(trip_master):
	"""Fetch Trip Path Log points sorted by timestamp"""
	if not trip_master:
		return []
	_check_trip_read(trip_master)
	return frappe.get_all(
		"Trip Path Log",
		filters={"trip_master": trip_master},
		fields=["latitude", "longitude", "timestamp", "employee_name", "activity_type"],
		order_by="timestamp asc",
	)


@frappe.whitelist()
def get_trip_itinerary(trip_master):
	"""Return Trip Master itinerary for Travel Request view"""
	if not trip_master:
		return {}

	if not frappe.has_permission("Trip Master", "read", trip_master):
		frappe.throw("Not permitted", frappe.PermissionError)

	trip = frappe.get_doc("Trip Master", trip_master)
	itinerary = []
	for row in trip.itinerary:
		itinerary.append({
			"from_city": row.from_city,
			"to_city": row.to_city,
			"departure_datetime": row.departure_datetime,
			"arrival_datetime": row.arrival_datetime,
		})

	return {
		"title": trip.title,
		"status": trip.status,
		"from_date": trip.from_date,
		"to_date": trip.to_date,
		"itinerary": itinerary,
	}


@frappe.whitelist()
def create_expense_claim_mobile(trip_master, employee, expense_type, amount, expense_date, description=None, attachment_url=None):
	"""Whitelisted wrapper for simplified mobile expense claim creation."""
	return create_expense_claim_mobile_service(
		trip_master,
		employee,
		expense_type,
		amount,
		expense_date,
		description,
		attachment_url,
	)
