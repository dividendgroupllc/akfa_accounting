# Copyright (c) 2025, Asadbek and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class TripPathLog(Document):
	"""Trip Path Log for geolocation tracking"""

	def before_save(self):
		"""Extract latitude and longitude from geolocation field"""
		if self.location and not (self.latitude and self.longitude):
			try:
				import json
				location_data = json.loads(self.location) if isinstance(self.location, str) else self.location

				if isinstance(location_data, dict):
					# Try GeoJSON FeatureCollection format first
					if location_data.get("type") == "FeatureCollection" and location_data.get("features"):
						first_feature = location_data["features"][0]
						geometry = first_feature.get("geometry", {})
						if geometry.get("type") == "Point" and geometry.get("coordinates"):
							coords = geometry["coordinates"]
							# GeoJSON format is [longitude, latitude]
							self.longitude = coords[0] if len(coords) > 0 else None
							self.latitude = coords[1] if len(coords) > 1 else None
					# Fallback to simple lat/lng object
					elif "latitude" in location_data or "lat" in location_data:
						self.latitude = location_data.get("latitude") or location_data.get("lat")
						self.longitude = location_data.get("longitude") or location_data.get("lng")
			except Exception as e:
				frappe.log_error(f"Error parsing geolocation: {e}", "Trip Path Log")
