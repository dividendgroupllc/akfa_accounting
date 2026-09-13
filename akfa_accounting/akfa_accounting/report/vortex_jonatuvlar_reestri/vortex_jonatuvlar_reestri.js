// Copyright (c) 2026, Asadbek and contributors
// License: see license.txt

frappe.query_reports["Vortex Jonatuvlar Reestri"] = {
	filters: [
		{ fieldname: "from_date", label: __("Dan"), fieldtype: "Date", default: frappe.datetime.month_start(), reqd: 1 },
		{ fieldname: "to_date", label: __("Gacha"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
		{ fieldname: "customer", label: __("Mijoz"), fieldtype: "Link", options: "Customer" },
		{ fieldname: "qabul_holati", label: __("Manager qabuli"), fieldtype: "Select", options: "\nKutilmoqda\nQabul qilindi" },
	],
};
