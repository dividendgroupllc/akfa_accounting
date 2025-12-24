# Copyright (c) 2025, Asadbek and contributors
# For license information, please see license.txt

"""
Provisioning Service

Handles Travel Request creation and cancellation for Trip Master.
"""

import frappe
from frappe import _


class ProvisioningService:
    """Service for provisioning Travel Requests"""

    def __init__(self, trip_master_doc):
        self.trip = trip_master_doc
        self.created_requests = []

    def create_travel_requests(self, project_name=None):
        """Create Travel Request for each member"""
        for member in self.trip.members:
            tr = self._create_single_request(member, project_name)
            member.travel_request = tr.name
            self.created_requests.append(tr.name)

        frappe.msgprint(
            _("{0} Travel Request(s) created").format(len(self.created_requests))
        )
        return self.created_requests

    def _create_single_request(self, member, project_name):
        """Create single Travel Request document"""
        tr = frappe.new_doc("Travel Request")
        tr.employee = member.employee
        tr.travel_type = "Domestic"
        tr.purpose_of_travel = "Business Meeting"  # Default purpose

        # Build itinerary route string
        itinerary_route = self._build_itinerary_route()
        itinerary_details = self._build_itinerary_details()
        tr.description = (
            f"Auto-created from Trip Master {self.trip.name} - {self.trip.purpose}\n"
            f"Route: {itinerary_route}\n"
            f"Schedule: {itinerary_details}"
        )

        # Link to Trip Master
        tr.custom_trip_master = self.trip.name

        # Link to Project if provided
        if project_name:
            tr.project = project_name

        # Add itinerary
        self._add_itinerary(tr)

        tr.flags.ignore_permissions = True
        tr.insert()
        tr.submit()

        return tr

    def _add_itinerary(self, tr):
        """Add itinerary rows to Travel Request from Trip Master itinerary"""
        if self.trip.itinerary and len(self.trip.itinerary) > 0:
            # Use multi-city itinerary with explicit legs
            for stop in self.trip.itinerary:
                tr.append(
                    "itinerary",
                    {
                        "travel_from": stop.from_city or self.trip.destination or "N/A",
                        "travel_to": stop.to_city or stop.from_city or self.trip.destination or "N/A",
                    },
                )
        else:
            # Fallback to single destination
            tr.append(
                "itinerary",
                {
                    "travel_from": self.trip.destination or "N/A",
                    "travel_to": self.trip.destination or "N/A",
                },
            )

    def _build_itinerary_route(self):
        """Build itinerary route string like 'Tashkent -> Samarkand -> Navoi'"""
        if self.trip.itinerary and len(self.trip.itinerary) > 0:
            legs = []
            for stop in self.trip.itinerary:
                if stop.from_city and stop.to_city:
                    legs.append(f"{stop.from_city} -> {stop.to_city}")
                elif stop.to_city:
                    legs.append(stop.to_city)
                elif stop.from_city:
                    legs.append(stop.from_city)
            return " | ".join(legs) if legs else "N/A"
        if self.trip.destination:
            return self.trip.destination
        return "N/A"

    def _build_itinerary_details(self):
        """Build human-readable itinerary schedule with datetimes"""
        if self.trip.itinerary and len(self.trip.itinerary) > 0:
            details = []
            for stop in self.trip.itinerary:
                leg = f"{stop.from_city or 'N/A'} -> {stop.to_city or 'N/A'}"
                if stop.departure_datetime or stop.arrival_datetime:
                    leg += f" ({stop.departure_datetime} - {stop.arrival_datetime})"
                details.append(leg)
            return " | ".join(details) if details else "N/A"
        return f"{self.trip.destination} ({self.trip.from_date} - {self.trip.to_date})"

    def cancel_travel_requests(self):
        """Cancel all linked Travel Requests"""
        for member in self.trip.members:
            if member.travel_request:
                self._cancel_single_request(member.travel_request)

    def _cancel_single_request(self, request_name):
        """Cancel a single Travel Request"""
        try:
            tr = frappe.get_doc("Travel Request", request_name)
            if tr.docstatus == 1:
                tr.flags.ignore_permissions = True
                tr.cancel()
                frappe.msgprint(_("Travel Request {0} cancelled").format(tr.name))
        except Exception as e:
            frappe.log_error(f"Error cancelling Travel Request {request_name}: {e}")

    def validate_members(self):
        """Validate trip members before provisioning"""
        self._validate_leader_exists()
        self._validate_unique_employees()

    def _validate_leader_exists(self):
        """Ensure exactly one leader is marked"""
        leaders = [m for m in self.trip.members if m.is_leader]
        if not leaders:
            frappe.throw(_("At least one member must be marked as Leader"))
        if len(leaders) > 1:
            frappe.throw(_("Only one member can be marked as Leader"))

    def _validate_unique_employees(self):
        """Ensure no duplicate employees"""
        employees = [m.employee for m in self.trip.members]
        if len(employees) != len(set(employees)):
            frappe.throw(_("Duplicate employees found in trip members"))

    def get_leader(self):
        """Get the leader from members"""
        for m in self.trip.members:
            if m.is_leader:
                return m
        return None
