import frappe

from akfa_accounting.api import get_active_trip, get_trip_balance
from akfa_accounting.events.login_redirect import redirect_employee


def login_probe(user, password):
	frappe.set_user(user)
	frappe.local.response = frappe._dict()
	redirect_employee()
	frappe.set_user("Administrator")
	return frappe.local.response


def permission_probe(user):
	frappe.set_user(user)
	trips = frappe.get_list("Trip Master", pluck="name")
	travel_requests = frappe.get_list("Travel Request", pluck="name")
	roles = frappe.get_roles(user)
	workspaces = frappe.get_list(
		"Workspace",
		filters={"module": "akfa_accounting"},
		fields=["name", "title", "restrict_to_domain"],
	)
	frappe.set_user("Administrator")
	return {
		"trips": trips,
		"travel_requests": travel_requests,
		"roles": roles,
		"workspaces": workspaces,
	}


def api_probe(user):
	employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if not employee:
		return {"error": "No employee"}

	frappe.set_user(user)
	active = get_active_trip(employee)
	trip_name = active.get("trip", {}).get("name") if active.get("trip") else None
	balance = get_trip_balance(trip_name) if trip_name else None
	frappe.set_user("Administrator")

	return {
		"employee": employee,
		"active_trip": active,
		"trip_balance": balance,
	}


def travel_request_perms():
	perms = frappe.permissions.get_all_perms("Travel Request")
	return {"perms": perms, "count": len(perms)}


def trip_master_perms():
	perms = frappe.permissions.get_all_perms("Trip Master")
	return {"perms": perms, "count": len(perms)}


def trip_master_pqc(user):
	from akfa_accounting.akfa_accounting.doctype.trip_master import trip_master
	return trip_master.get_permission_query_conditions(user)


def trip_list_for_user(user):
	frappe.set_user(user)
	trips = frappe.get_list("Trip Master", pluck="name")
	frappe.set_user("Administrator")
	return trips


def list_users(prefix):
	users = frappe.get_all("User", filters=[["name", "like", prefix]], pluck="name")
	return {"users": users}
