# Copyright (c) 2025, Asadbek and contributors
# For license information, please see license.txt

from frappe import _


def get_data():
	return [
		{
			"module_name": "akfa_accounting",
			"category": "Modules",
			"label": _("AKFA Accounting"),
			"color": "#FF5733",
			"icon": "fa fa-briefcase",
			"type": "module",
			"description": "Trip Master and Accounting Management"
		}
	]
