"""Drop the stale "Mobile HR" Page record.

The page JSON used to declare `name: "Mobile HR"` with `module: "Akfa Accounting"`.
Frappe expects a Page to be named by its slug, so `/app/mobile-hr` resolved to
nothing and the desk answered "No permission for Page".

The JSON now declares `name: "mobile-hr"`, which migrate installs on its own.
This patch only removes the old record so the two do not sit side by side.
"""

import frappe

STALE = "Mobile HR"
CORRECT = "mobile-hr"


def execute():
	if not frappe.db.exists("Page", STALE):
		return

	# Only drop the stale row once the correct page is actually in place.
	if not frappe.db.exists("Page", CORRECT):
		return

	frappe.delete_doc("Page", STALE, force=1, ignore_permissions=True, delete_permanently=True)
