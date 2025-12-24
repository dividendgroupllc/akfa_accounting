import frappe


def execute():
	if not frappe.db.exists("DocType", "Trip Master"):
		return

	_ensure_perm(
		parent="Trip Master",
		role="System Manager",
		updates={
			"read": 1,
			"write": 1,
			"create": 1,
			"submit": 1,
			"cancel": 1,
		},
	)
	_ensure_perm(
		parent="Trip Master",
		role="Employee",
		updates={
			"read": 1,
		},
	)


def _ensure_perm(parent, role, updates):
	existing = frappe.get_all(
		"Custom DocPerm",
		filters={"parent": parent, "role": role, "permlevel": 0},
	)
	if existing:
		return

	docperm = frappe.get_doc(
		{
			"doctype": "Custom DocPerm",
			"parent": parent,
			"parenttype": "DocType",
			"parentfield": "permissions",
			"role": role,
			"permlevel": 0,
			**updates,
		}
	)
	docperm.flags.ignore_permissions = True
	docperm.insert()
