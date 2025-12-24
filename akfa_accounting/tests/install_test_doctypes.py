#!/usr/bin/env python3
# Copyright (c) 2025, Asadbek and contributors
# For license information, please see license.txt

"""
Install Trip Master DocTypes to database manually
Run with: bench --site akfa.local execute akfa_accounting.tests.install_test_doctypes.install
"""

import frappe
import json
import os


def install():
	"""Install Trip Master DocTypes to database"""
	print("\n" + "="*70)
	print("Installing Trip Master DocTypes")
	print("="*70 + "\n")

	doctypes_to_install = [
		"Trip Member",
		"Trip Vehicle",
		"Trip Master",
		"Trip Path Log"
	]

	app_path = frappe.get_app_path("akfa_accounting")

	for doctype in doctypes_to_install:
		doctype_path = doctype.lower().replace(" ", "_")
		json_path = os.path.join(
			app_path,
			"akfa_accounting",
			"doctype",
			doctype_path,
			f"{doctype_path}.json"
		)

		if not os.path.exists(json_path):
			print(f"❌ File not found: {json_path}")
			continue

		try:
			with open(json_path, 'r') as f:
				doctype_json = json.load(f)

			# Check if already exists
			if frappe.db.exists("DocType", doctype):
				print(f"⚠️  {doctype} already exists, skipping...")
				continue

			# Insert DocType
			doc = frappe.get_doc(doctype_json)
			doc.flags.ignore_mandatory = True
			doc.flags.ignore_permissions = True
			doc.insert()

			frappe.db.commit()
			print(f"✅ Installed: {doctype}")

		except Exception as e:
			print(f"❌ Error installing {doctype}: {e}")
			frappe.db.rollback()

	print("\n" + "="*70)
	print("Installation Complete")
	print("="*70 + "\n")


if __name__ == "__main__":
	install()
