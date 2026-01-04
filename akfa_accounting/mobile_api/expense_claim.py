import frappe
from frappe import _
from frappe.utils import nowdate, flt


@frappe.whitelist()
def create_expense_from_mobile(trip_master, expense_type, amount, description=None, receipt_url=None):
	"""API for mobile app to create expense claim"""
	try:
		employee = _get_session_employee()
		return create_expense_claim_mobile(trip_master, employee, expense_type, float(amount), nowdate(), description, receipt_url)
	except Exception as err:
		frappe.log_error(f"Mobile expense error: {err}", "Mobile API Error")
		frappe.throw(str(err))


def create_expense_claim_mobile(trip_master, employee, expense_type, amount, expense_date, description=None, attachment_url=None):
	try:
		session_employee = _get_session_employee()
		_enforce_employee_scope(employee, session_employee)

		trip = _load_active_trip(trip_master, employee)
		employee_doc = _load_employee(employee)
		_validate_expense_type(expense_type)

		claim = _build_expense_claim(
			trip,
			employee_doc,
			expense_type,
			amount,
			expense_date,
			description,
		)

		_attach_file(claim, attachment_url)
		frappe.db.commit()

		return _success_payload(claim)
	except Exception as err:
		frappe.log_error(f"Error creating expense claim: {err}", "Mobile API Error")
		frappe.throw(_("Failed to create expense claim: {0}").format(err))


def _get_session_employee():
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Authentication required"), frappe.PermissionError)

	employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if not employee:
		frappe.throw(_("No employee linked to user {0}").format(user), frappe.PermissionError)
	return employee


def _enforce_employee_scope(requested_employee, session_employee):
	if requested_employee != session_employee:
		frappe.local.response["http_status_code"] = 403
		frappe.throw(
			_("Forbidden: You can only create expense claims for your own employee account"),
			frappe.PermissionError,
		)


def _load_active_trip(trip_master, employee):
	trip = frappe.get_doc("Trip Master", trip_master)
	if trip.docstatus != 1:
		frappe.throw(_("Trip Master {0} is not submitted").format(trip_master))
	if not any(m.employee == employee for m in trip.members):
		frappe.local.response["http_status_code"] = 403
		frappe.throw(
			_("Forbidden: Employee {0} is not a member of Trip {1}").format(employee, trip_master),
			frappe.PermissionError,
		)
	return trip


def _load_employee(employee):
	emp = frappe.get_doc("Employee", employee)
	if not emp.company:
		frappe.throw(_("Employee {0} does not have a company assigned").format(employee))
	return emp


def _validate_expense_type(expense_type):
	if frappe.db.exists("Expense Claim Type", expense_type):
		return
	frappe.throw(_("Expense Claim Type '{0}' does not exist").format(expense_type))


def _build_expense_claim(trip, employee_doc, expense_type, amount, expense_date, description):
	claim = _new_claim(trip, employee_doc)
	_set_company_defaults(claim, employee_doc.company)
	_add_expense_row(claim, expense_type, amount, expense_date, description)
	
	# Link to Employee Advance if exists for this trip
	_link_employee_advance(claim, trip.name, employee_doc.name, amount)
	
	claim.flags.ignore_permissions = True
	claim.insert()
	# Auto-submit for streamlined workflow
	claim.submit()
	return claim


def _new_claim(trip, employee_doc):
	claim = frappe.new_doc("Expense Claim")
	claim.employee = employee_doc.name
	claim.employee_name = employee_doc.employee_name
	claim.company = employee_doc.company
	claim.posting_date = nowdate()
	claim.custom_trip_master = trip.name
	claim.project = trip.project
	claim.approval_status = "Approved"  # Auto-approve so admin can submit
	return claim


def _set_company_defaults(claim, company):
	payable_account = frappe.db.get_value("Company", company, "default_payable_account")
	cost_center = frappe.db.get_value("Company", company, "cost_center")
	if payable_account:
		claim.payable_account = payable_account
	if cost_center:
		claim.cost_center = cost_center


def _add_expense_row(claim, expense_type, amount, expense_date, description):
	# Get cost center from claim or company default
	cost_center = claim.cost_center
	if not cost_center and claim.company:
		cost_center = frappe.db.get_value("Company", claim.company, "cost_center")
	
	claim.append(
		"expenses",
		{
			"expense_type": expense_type,
			"expense_date": expense_date,
			"amount": float(amount),
			"sanctioned_amount": float(amount),
			"description": description or f"Expense from mobile app - {expense_type}",
			"cost_center": cost_center,
		},
	)


def _link_employee_advance(claim, trip_master, employee, amount):
	"""Link expense claim to employee advance for this trip"""
	# Find submitted employee advance for this trip and employee
	advance = frappe.db.get_value(
		"Employee Advance",
		{
			"custom_trip_master": trip_master,
			"employee": employee,
			"docstatus": 1,
		},
		["name", "advance_amount", "paid_amount", "claimed_amount", "status"],
		as_dict=True
	)
	
	if not advance:
		# No advance found, expense will be "Unpaid" - reimbursement workflow
		return
	
	# Get advance document
	advance_doc = frappe.get_doc("Employee Advance", advance.name)
	
	# Calculate unclaimed based on whether advance is paid or not
	# If advance is "Paid" - use paid_amount, otherwise use advance_amount (pending payment)
	if advance.status == "Paid":
		available = flt(advance.paid_amount) - flt(advance.claimed_amount)
	else:
		# Advance approved but not yet paid - still allocate from advance_amount
		available = flt(advance.advance_amount) - flt(advance.claimed_amount)
	
	if available <= 0:
		# Advance fully used, expense will be "Unpaid"
		return
	
	# Allocate from advance (up to expense amount or available amount)
	allocated = min(flt(amount), available)
	
	# Add to advances child table
	claim.append(
		"advances",
		{
			"employee_advance": advance.name,
			"posting_date": advance_doc.posting_date,
			"advance_paid": flt(advance.paid_amount) if advance.status == "Paid" else flt(advance.advance_amount),
			"unclaimed_amount": available,
			"allocated_amount": allocated,
			"advance_account": advance_doc.advance_account,
		},
	)


def _attach_file(claim, attachment_url):
	if not attachment_url:
		return

	try:
		file_doc = frappe.get_doc(
			{
				"doctype": "File",
				"file_url": attachment_url,
				"attached_to_doctype": "Expense Claim",
				"attached_to_name": claim.name,
				"folder": "Home/Attachments",
				"is_private": 0,
			}
		)
		file_doc.flags.ignore_permissions = True
		file_doc.insert()
	except Exception as err:
		frappe.log_error(f"Error attaching file: {err}", "Mobile API File Attachment Error")


def _success_payload(claim):
	# Reload to get updated status
	claim.reload()
	return {
		"success": True,
		"message": _("Expense Claim submitted successfully"),
		"expense_claim_id": claim.name,
		"expense_claim_url": frappe.utils.get_url_to_form("Expense Claim", claim.name),
		"total_amount": claim.total_claimed_amount,
		"status": claim.status,
		"advance_used": flt(claim.total_advance_amount) > 0,
	}
