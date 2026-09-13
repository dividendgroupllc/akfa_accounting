# Copyright (c) 2026, Asadbek and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class CustomerSite(Document):
	def validate(self):
		self.site_name = (self.site_name or "").strip()
		if not self.site_name:
			frappe.throw(_("Site Name is required"))

		# Bitta mijozda bir xil nomli ikkita obyekt bo'lmasin. Hujjat nomi
		# seriyadan (SITE-.#####) olinadi -- ya'ni site_name ni keyin bemalol
		# tuzatsa bo'ladi -- shuning uchun takrorlanishni faqat shu tekshiruv
		# ushlab turadi.
		filters = {"customer": self.customer, "site_name": self.site_name}
		if not self.is_new():
			filters["name"] = ("!=", self.name)

		if frappe.db.exists("Customer Site", filters):
			frappe.throw(
				_("Site {0} already exists for customer {1}").format(
					frappe.bold(self.site_name), frappe.bold(self.customer)
				)
			)
