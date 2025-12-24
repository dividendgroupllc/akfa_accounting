# Copyright (c) 2025, Asadbek and contributors
# For license information, please see license.txt

"""
Fleet Service

Handles Vehicle status management for Trip Master.
"""

import frappe
from frappe import _


class FleetService:
    """Service for managing vehicle statuses"""

    def __init__(self, trip_master_doc):
        self.trip = trip_master_doc

    def allocate_vehicles(self):
        """Set vehicle status to 'In Trip' and link to trip"""
        for vehicle in self.trip.vehicles:
            self._set_vehicle_in_trip(vehicle)

        if self.trip.vehicles:
            frappe.msgprint(
                _("{0} Vehicle(s) allocated to trip").format(len(self.trip.vehicles))
            )

    def _set_vehicle_in_trip(self, vehicle_row):
        """Set single vehicle to In Trip status"""
        # Get vehicle document
        vehicle_doc = frappe.get_doc("Vehicle", vehicle_row.vehicle)

        # Store previous status
        vehicle_row.previous_status = vehicle_doc.custom_trip_status or "Available"

        # Update vehicle status
        vehicle_doc.custom_trip_status = "In Trip"
        vehicle_doc.custom_current_trip = self.trip.name
        vehicle_doc.flags.ignore_permissions = True
        vehicle_doc.flags.ignore_mandatory = True
        vehicle_doc.save()

    def release_vehicles(self):
        """Release vehicles back to Available status"""
        for vehicle in self.trip.vehicles:
            self._release_single_vehicle(vehicle)

        if self.trip.vehicles:
            frappe.msgprint(
                _("{0} Vehicle(s) released").format(len(self.trip.vehicles))
            )

    def _release_single_vehicle(self, vehicle_row):
        """Release single vehicle"""
        vehicle_doc = frappe.get_doc("Vehicle", vehicle_row.vehicle)

        restore_status = vehicle_row.previous_status or "Available"
        vehicle_doc.custom_trip_status = restore_status
        vehicle_doc.custom_current_trip = None
        vehicle_doc.flags.ignore_permissions = True
        vehicle_doc.flags.ignore_mandatory = True
        vehicle_doc.save()

    def validate_availability(self):
        """Ensure all vehicles are available"""
        for vehicle in self.trip.vehicles:
            self._check_vehicle_available(vehicle.vehicle)

    def _check_vehicle_available(self, vehicle_name):
        """Check if vehicle is available"""
        status = frappe.db.get_value("Vehicle", vehicle_name, "custom_trip_status")
        if status and status != "Available":
            frappe.throw(
                _("Vehicle {0} is not available. Current status: {1}").format(
                    vehicle_name, status
                )
            )


def get_fleet_summary():
    """
    Get fleet summary statistics

    Returns:
        dict: Fleet statistics including total, in_trip, and available counts
    """
    vehicles = frappe.get_all(
        "Vehicle",
        fields=["name", "custom_trip_status"],
        filters={"disabled": 0}
    )

    total = len(vehicles)
    in_trip = sum(1 for v in vehicles if v.custom_trip_status == "In Trip")
    available = sum(1 for v in vehicles if not v.custom_trip_status or v.custom_trip_status == "Available")

    return {
        "total": total,
        "in_trip": in_trip,
        "available": available,
        "maintenance": total - in_trip - available
    }
