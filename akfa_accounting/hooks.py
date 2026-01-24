app_name = "akfa_accounting"
app_title = "akfa_accounting"
app_publisher = "Asadbek"
app_description = "akfa_accounting"
app_email = "asadbek.backend@gmail.com"
app_license = "mit"

doctype_js = {
	"Payment Entry": "public/js/payment_entry.js",
	"Travel Request": "public/js/travel_request.js",
	"Expense Claim": "public/js/expense_claim.js",
}

app_include_js = ["/assets/akfa_accounting/js/pwa_init.js"]

fixtures = [
	{
		"dt": "Custom Field",
		"filters": [["dt", "in", ["Payment Entry", "Vehicle", "Travel Request", "Employee Advance", "Expense Claim", "Project", "Expense Claim Detail"]]],
	},
	{
		"dt": "Property Setter",
		"filters": [["doc_type", "in", ["Project", "Vehicle", "Travel Request", "Expense Claim", "Expense Claim Detail"]]],
	},
	{
		"dt": "Print Format",
		"filters": [["module", "=", "akfa_accounting"]],
	},
	{
		"dt": "Workspace",
		"filters": [["module", "=", "akfa_accounting"]],
	},
]

permission_query_conditions = {
	"Trip Master": "akfa_accounting.akfa_accounting.doctype.trip_master.trip_master.get_permission_query_conditions",
}

has_permission = {
	"Trip Master": "akfa_accounting.akfa_accounting.doctype.trip_master.trip_master.has_permission",
}

doc_events = {
	"Expense Claim": {
		"validate": "akfa_accounting.validations.expense_claim.validate_trip_membership",
	},
	"Employee Advance": {
		"on_submit": "akfa_accounting.events.employee_advance.auto_create_payment_entry",
	}
}

on_login = "akfa_accounting.events.login_redirect.redirect_employee"
