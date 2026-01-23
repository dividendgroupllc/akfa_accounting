// Copyright (c) 2026, Asadbek and contributors
// For license information, please see license.txt

frappe.query_reports["Cash Distribution Report"] = {
"filters": [
{
"fieldname": "from_date",
"label": __("From Date"),
"fieldtype": "Date",
"default": frappe.datetime.add_days(frappe.datetime.get_today(), -10),
"reqd": 1
},
{
"fieldname": "to_date",
"label": __("To Date"),
"fieldtype": "Date",
"default": frappe.datetime.get_today(),
"reqd": 1
},
{
"fieldname": "currency",
"label": __("Currency"),
"fieldtype": "Link",
"options": "Currency",
"get_query": function() {
return {
filters: {
"name": ["in", ["USD", "UZS"]]
}
};
}
}
],

"formatter": function(value, row, column, data, default_formatter) {
value = default_formatter(value, row, column, data);

if (!data) return value;

// Bold for section headers and totals
if (data.bold) {
value = "<strong>" + value + "</strong>";
}

// Highlight section headers
if (data.section && data.section.includes("TARQATILMAGAN")) {
if (column.fieldname === "section") {
value = "<span style='color: #e74c3c; font-weight: bold;'>" + value + "</span>";
}
}
if (data.section && data.section.includes("TARQATILGAN YOZUV")) {
if (column.fieldname === "section") {
value = "<span style='color: #27ae60; font-weight: bold;'>" + value + "</span>";
}
}
if (data.section && data.section.includes("KUNLIK")) {
if (column.fieldname === "section") {
value = "<span style='color: #3498db; font-weight: bold;'>" + value + "</span>";
}
}

// Highlight JAMI rows
if (data.section && data.section.includes("JAMI")) {
value = "<strong style='background-color: #f0f0f0; padding: 2px 5px;'>" + value + "</strong>";
}

// Qoldiq with balance > 0
if (data.section === "Qoldiq" && data.amount > 0) {
if (column.fieldname === "amount") {
value = "<span style='color: #e74c3c; font-weight: bold;'>" + value + "</span>";
}
}

return value;
}
};
