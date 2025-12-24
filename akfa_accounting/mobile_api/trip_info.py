import frappe
from frappe import _


def get_active_trip(employee):
	try:
		trip = _find_active_trip(employee)
		return {
			"success": True,
			"trip": trip,
			"message": _("No active trip found for employee") if not trip else None,
		}
	except Exception as err:
		frappe.log_error(f"Error getting active trip: {err}", "Mobile API Error")
		frappe.throw(_("Failed to get active trip: {0}").format(err))


def get_trip_balance(trip_id):
	try:
		trip = _load_submitted_trip(trip_id)
		project = _load_linked_project(trip)
		budget = project.estimated_costing or 0
		spent = _calculate_spent(trip_id)
		advances = _calculate_advances(trip_id)
		total_spent = spent + advances
		utilization = (total_spent / budget * 100) if budget else 0

		return {
			"success": True,
			"trip_id": trip_id,
			"trip_title": trip.title,
			"budget": budget,
			"spent": total_spent,
			"balance": budget - total_spent,
			"utilization_percent": round(utilization, 2),
			"currency": trip.currency or "UZS",
			"status": trip.status,
		}
	except Exception as err:
		frappe.log_error(f"Error getting trip balance: {err}", "Mobile API Error")
		return {"success": False, "error": str(err)}


def _find_active_trip(employee):
	trips = frappe.get_all(
		"Trip Master",
		filters={"docstatus": 1, "status": "Active"},
		fields=["name", "title", "from_date", "to_date", "destination"],
	)

	for trip in trips:
		member = frappe.db.exists("Trip Member", {"parent": trip.name, "employee": employee})
		if member:
			return {
				"name": trip.name,
				"title": trip.title,
				"from_date": trip.from_date,
				"to_date": trip.to_date,
				"destination": trip.destination,
				"is_leader": _is_leader(trip.name, employee),
			}
	return None


def _is_leader(trip_name, employee):
	return bool(
		frappe.db.exists(
			"Trip Member",
			{"parent": trip_name, "employee": employee, "is_leader": 1},
		)
	)


def _load_submitted_trip(trip_id):
	trip = frappe.get_doc("Trip Master", trip_id)
	if trip.docstatus != 1:
		frappe.throw(_("Trip Master {0} is not submitted").format(trip_id))
	return trip


def _load_linked_project(trip):
	if not trip.project:
		frappe.throw(_("No project linked to Trip Master {0}").format(trip.name))
	return frappe.get_doc("Project", trip.project)


def _calculate_spent(trip_id):
	expense_claims = frappe.get_all(
		"Expense Claim",
		filters={"custom_trip_master": trip_id, "docstatus": 1},
		fields=["total_claimed_amount"],
	)
	return sum((claim.total_claimed_amount or 0) for claim in expense_claims)


def _calculate_advances(trip_id):
	advances = frappe.get_all(
		"Employee Advance",
		filters={"custom_trip_master": trip_id, "docstatus": 1, "status": "Paid"},
		fields=["paid_amount"],
	)
	return sum((adv.paid_amount or 0) for adv in advances)
