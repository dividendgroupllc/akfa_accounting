"""
Auto-approve expense claims when submitted
"""

import frappe


def auto_approve_on_submit(doc, method):
	"""
	Auto-approve ALL expense claims when submitted
	This allows direct submission without waiting for manual approval
	"""
	if doc.docstatus == 1:  # Being submitted
		# Auto-approve if not already approved/rejected
		if not doc.approval_status or doc.approval_status == 'Draft':
			doc.approval_status = 'Approved'
			frappe.msgprint(
				msg=frappe._('Expense claim has been auto-approved'),
				title=frappe._('Auto-Approved'),
				indicator='green'
			)
