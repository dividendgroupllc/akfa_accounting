# Copyright (c) 2025, Asadbek and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class TripPathLog(Document):
	"""Trip Path Log for geolocation tracking"""

	def before_save(self):
		"""Extract latitude and longitude from geolocation field"""
		if self.location:
			try:
				import json
				location_data = json.loads(self.location) if isinstance(self.location, str) else self.location

				if isinstance(location_data, dict):
					self.latitude = location_data.get("latitude") or location_data.get("lat")
					self.longitude = location_data.get("longitude") or location_data.get("lng")
			except Exception as e:
				frappe.log_error(f"Error parsing geolocation: {e}", "Trip Path Log")
