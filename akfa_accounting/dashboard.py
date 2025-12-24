# Copyright (c) 2025, Asadbek and contributors
# For license information, please see license.txt

"""
Dashboard APIs for Trip Master system
"""

import frappe
from frappe import _


@frappe.whitelist()
def get_fleet_status():
	"""
	Get vehicle fleet status for dashboard

	Returns:
		dict: Vehicle status statistics
	"""
	vehicles = frappe.get_all(
		"Vehicle",
		fields=["name", "custom_trip_status"],
		filters={"disabled": 0}
	)

	total = len(vehicles)
	in_trip = sum(1 for v in vehicles if v.custom_trip_status == "In Trip")
	available = sum(1 for v in vehicles if not v.custom_trip_status or v.custom_trip_status == "Available")
	maintenance = total - in_trip - available

	return {
		"total": total,
		"in_trip": in_trip,
		"available": available,
		"maintenance": maintenance,
		"labels": ["Available", "In Trip", "Maintenance"],
		"values": [available, in_trip, maintenance],
		"colors": ["#28a745", "#ffc107", "#dc3545"]
	}


@frappe.whitelist()
def get_budget_summary():
	"""
	Get budget summary for all active trips

	Returns:
		dict: Budget statistics
	"""
	# Get all active trips
	active_trips = frappe.get_all(
		"Trip Master",
		filters={
			"docstatus": 1,
			"status": "Active"
		},
		fields=["name", "budget_amount", "currency"]
	)

	total_budget = sum(trip.budget_amount or 0 for trip in active_trips)

	# Calculate actual spend from Employee Advances and Expense Claims
	total_spent = 0

	for trip in active_trips:
		# Get Employee Advances for this trip
		advances = frappe.get_all(
			"Employee Advance",
			filters={
				"custom_trip_master": trip.name,
				"docstatus": 1
			},
			fields=["paid_amount"]
		)
		total_spent += sum(adv.paid_amount or 0 for adv in advances)

		# Get Expense Claims for this trip
		claims = frappe.get_all(
			"Expense Claim",
			filters={
				"custom_trip_master": trip.name,
				"docstatus": 1
			},
			fields=["total_claimed_amount"]
		)
		total_spent += sum(claim.total_claimed_amount or 0 for claim in claims)

	utilization_percent = (total_spent / total_budget * 100) if total_budget > 0 else 0

	return {
		"total_budget": total_budget,
		"total_spent": total_spent,
		"remaining": total_budget - total_spent,
		"utilization_percent": round(utilization_percent, 2),
		"currency": active_trips[0].currency if active_trips else "USD"
	}


@frappe.whitelist()
def get_active_trips_count():
	"""
	Get count of active trips

	Returns:
		dict: Active trips statistics
	"""
	active_count = frappe.db.count(
		"Trip Master",
		filters={
			"docstatus": 1,
			"status": "Active"
		}
	)

	total_employees_on_trip = 0
	total_vehicles_in_use = 0

	active_trips = frappe.get_all(
		"Trip Master",
		filters={
			"docstatus": 1,
			"status": "Active"
		},
		fields=["name"]
	)

	for trip in active_trips:
		trip_doc = frappe.get_doc("Trip Master", trip.name)
		total_employees_on_trip += len(trip_doc.members)
		total_vehicles_in_use += len(trip_doc.vehicles)

	return {
		"active_trips": active_count,
		"total_employees": total_employees_on_trip,
		"total_vehicles": total_vehicles_in_use
	}


@frappe.whitelist()
def get_trip_master_dashboard_data():
	"""
	Get complete dashboard data for Trip Master

	Returns:
		dict: Complete dashboard statistics
	"""
	return {
		"fleet_status": get_fleet_status(),
		"budget_summary": get_budget_summary(),
		"active_trips": get_active_trips_count()
	}
