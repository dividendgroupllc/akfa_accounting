import frappe


def execute():
	if frappe.db.exists("Workspace", "Akfa HR"):
		return

	doc = frappe.get_doc(
		{
			"doctype": "Workspace",
			"name": "Akfa HR",
			"title": "Akfa HR",
			"label": "Akfa HR",
			"module": "akfa_accounting",
			"public": 1,
			"icon": "user",
			"content": '[{"id":"hdr_akfa_hr","type":"header","data":{"text":"<span class=\\"h4\\">Akfa HR</span>","col":12}},{"id":"shortcut_travel_request","type":"shortcut","data":{"shortcut_name":"Travel Request","col":3}},{"id":"shortcut_expense_claim","type":"shortcut","data":{"shortcut_name":"Expense Claim","col":3}}]',
			"shortcuts": [
				{
					"label": "Travel Request",
					"link_to": "Travel Request",
					"type": "DocType",
					"doc_view": "List",
					"color": "Green",
				},
				{
					"label": "Expense Claim",
					"link_to": "Expense Claim",
					"type": "DocType",
					"doc_view": "List",
					"color": "Orange",
				},
			],
			"roles": [
				{"role": "Employee"},
				{"role": "System Manager"},
			],
		}
	)
	doc.flags.ignore_permissions = True
	doc.insert()
