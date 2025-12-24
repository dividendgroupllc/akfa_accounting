import json
import os

import frappe


def execute():
	if not frappe.db.exists("Website Settings", "Website Settings"):
		return

	_ensure_manifest_field()
	settings = frappe.get_doc("Website Settings", "Website Settings")

	manifest = _load_manifest(settings.get("manifest_json"))
	manifest["start_url"] = "/app"

	icon_path = _resolve_icon_path()
	if icon_path:
		settings.app_logo = icon_path

	settings.manifest_json = json.dumps(manifest)
	settings.save(ignore_permissions=True)


def _ensure_manifest_field():
	if frappe.db.exists("Custom Field", {"dt": "Website Settings", "fieldname": "manifest_json"}):
		return

	custom_field = frappe.get_doc(
		{
			"doctype": "Custom Field",
			"dt": "Website Settings",
			"fieldname": "manifest_json",
			"fieldtype": "Code",
			"label": "Manifest JSON",
			"insert_after": "app_logo",
			"read_only": 0,
			"hidden": 0,
		}
	)
	custom_field.flags.ignore_permissions = True
	custom_field.insert()


def _load_manifest(raw_manifest):
	if not raw_manifest:
		return {}
	try:
		return json.loads(raw_manifest)
	except Exception:
		return {}


def _resolve_icon_path():
	candidates = [
		("akfa_accounting", "public", "icons", "akfa-icon.png"),
		("akfa_accounting", "public", "icons", "akfa-icon.svg"),
	]
	for parts in candidates:
		path = frappe.get_app_path(*parts)
		if os.path.exists(path):
			return f"/assets/akfa_accounting/icons/{parts[-1]}"
	return None
