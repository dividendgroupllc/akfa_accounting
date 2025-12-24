import frappe


def redirect_employee(login_manager=None):
	user = getattr(login_manager, "user", None) or frappe.session.user
	if user == "Guest":
		return

	roles = set(frappe.get_roles(user))
	if "Employee" in roles and "System Manager" not in roles:
		frappe.local.response["redirect_to"] = "/app/akfa-hr"
