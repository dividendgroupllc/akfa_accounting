import frappe
from frappe import _


@frappe.whitelist()
def get_active_trip(employee=None):
	try:
		# Auto-detect employee from session if not provided
		if not employee:
			user = frappe.session.user
			employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
			if not employee:
				return {"success": False, "trip": None, "employee": None, "message": _("No employee linked to user")}
		
		trip = _find_active_trip(employee)
		return {
			"success": True,
			"trip": trip,
			"employee": employee,
			"message": _("Hozirda aktiv safaringiz yo'q") if not trip else None,
		}
	except Exception as err:
		frappe.log_error(f"Error getting active trip: {err}", "Mobile API Error")
		return {"success": False, "trip": None, "employee": None, "message": str(err)}


def get_trip_balance(trip_id):
	try:
		trip = _load_submitted_trip(trip_id)
		project = _load_linked_project(trip)
		budget = project.estimated_costing or 0

		# Calculate actual spent amount (only Expense Claims)
		# Employee Advance is prepaid funds, not actual expenses
		spent = _calculate_spent(trip_id)

		# Calculate utilization based on actual expenses only
		utilization = (spent / budget * 100) if budget else 0

		return {
			"success": True,
			"trip_id": trip_id,
			"trip_title": trip.title,
			"budget": budget,
			"spent": spent,  # Only actual expenses (Expense Claims)
			"balance": budget - spent,
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
