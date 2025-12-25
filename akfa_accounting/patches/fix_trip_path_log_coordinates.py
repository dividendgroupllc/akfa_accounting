"""
Fix existing Trip Path Log records with incorrect latitude/longitude
"""

import frappe
import json


def execute():
	"""Update all Trip Path Log records that have location data but lat/long are 0"""
	logs = frappe.get_all(
		"Trip Path Log",
		filters=[
			["location", "!=", ""],
			["latitude", "=", 0],
			["longitude", "=", 0]
		],
		fields=["name", "location"]
	)

	updated = 0
	failed = 0

	for log_data in logs:
		try:
			log = frappe.get_doc("Trip Path Log", log_data.name)

			if not log.location:
				continue

			# Parse the location JSON
			location_data = json.loads(log.location) if isinstance(log.location, str) else log.location

			if not isinstance(location_data, dict):
				continue

			# Extract coordinates from GeoJSON FeatureCollection
			if location_data.get("type") == "FeatureCollection" and location_data.get("features"):
				first_feature = location_data["features"][0]
				geometry = first_feature.get("geometry", {})
				if geometry.get("type") == "Point" and geometry.get("coordinates"):
					coords = geometry["coordinates"]
					# GeoJSON format is [longitude, latitude]
					log.longitude = coords[0] if len(coords) > 0 else 0
					log.latitude = coords[1] if len(coords) > 1 else 0

					# Save without triggering hooks again
					log.db_update()
					updated += 1

		except Exception as e:
			frappe.log_error(f"Failed to fix {log_data.name}: {str(e)}", "Fix Trip Path Log")
			failed += 1

	frappe.db.commit()

	print(f"Updated {updated} records, failed {failed} records")
