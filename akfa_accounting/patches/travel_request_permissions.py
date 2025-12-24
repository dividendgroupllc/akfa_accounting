import frappe


def execute():
	if not frappe.db.exists("DocType", "Travel Request"):
		return

	if frappe.db.exists(
		"Custom DocPerm",
		{
			"parent": "Travel Request",
			"role": "Employee",
			"permlevel": 0,
		},
	):
		return

	docperm = frappe.get_doc(
		{
			"doctype": "Custom DocPerm",
			"parent": "Travel Request",
			"parenttype": "DocType",
			"parentfield": "permissions",
			"role": "Employee",
			"permlevel": 0,
			"read": 1,
		}
	)
	docperm.flags.ignore_permissions = True
	docperm.insert()
