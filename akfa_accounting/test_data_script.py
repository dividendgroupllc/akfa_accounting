import frappe
from frappe.utils import now_datetime, add_days, add_to_date

def execute():
    frappe.db.commit()
    print("--- Test Data Yaratish Boshlandi (V2) ---")

    # 0. Ensure Fiscal Year
    current_year = now_datetime().year
    year_name = str(current_year)
    company = frappe.db.get_single_value("Global Defaults", "default_company") or "My Company"
    company_currency = frappe.db.get_value("Company", company, "default_currency")
    
    if not frappe.db.exists("Fiscal Year", year_name):
        frappe.get_doc({
            "doctype": "Fiscal Year",
            "year": year_name,
            "year_start_date": f"{year_name}-01-01",
            "year_end_date": f"{year_name}-12-31",
            "companies": [{"company": company}]
        }).insert(ignore_permissions=True)
        print(f"Fiscal Year {year_name} yaratildi.")

    # 1. Employee
    employee = frappe.db.get_value("Employee", {"user_id": "Administrator"}, "name")
    if not employee:
        employee = frappe.get_doc({
            "doctype": "Employee",
            "first_name": "Administrator",
            "company": company,
            "user_id": "Administrator",
            "status": "Active",
            "gender": "Male",
            "date_of_birth": "1990-01-01",
            "date_of_joining": now_datetime().strftime("%Y-%m-%d")
        }).insert(ignore_permissions=True).name
        print(f"Employee yaratildi: {employee}")
    else:
        print(f"Employee topildi: {employee}")

    # 2. Trip Master V2
    trip_title = "Samarqand Biznes Forumi V2"
    if not frappe.db.exists("Trip Master", {"title": trip_title}):
        trip = frappe.get_doc({
            "doctype": "Trip Master",
            "title": trip_title,
            "posting_date": now_datetime().strftime("%Y-%m-%d"),
            "company": company,
            "purpose": "Yillik hisobot va hamkorlar bilan uchrashuv",
            "from_date": now_datetime().strftime("%Y-%m-%d"),
            "to_date": add_days(now_datetime(), 3).strftime("%Y-%m-%d"),
            "destination": "Samarqand, Registon Plaza",
            "budget_amount": 500,
            "currency": company_currency,
            "status": "Active",
            "members": [{"employee": employee, "employee_name": frappe.db.get_value("Employee", employee, "employee_name"), "is_leader": 1}]
        })
        trip.insert(ignore_permissions=True)
        trip.submit()
        print(f"Trip Master yaratildi: {trip.name}")
    else:
        trip = frappe.get_doc("Trip Master", {"title": trip_title})
        print(f"Trip Master topildi: {trip.name}")

    # 3. Expense Claim V2
    # Find Accounts & Cost Center
    payable_account = frappe.db.get_value("Account", {"account_type": "Payable", "company": company, "account_currency": company_currency}, "name")
    if not payable_account:
         payable_account = frappe.db.get_value("Account", {"account_type": "Payable", "company": company}, "name")

    cost_center = frappe.db.get_value("Cost Center", {"is_group": 0, "company": company}, "name")
    if not cost_center:
        cost_center = "Main - " + frappe.db.get_value("Company", company, "abbr")
        if not frappe.db.exists("Cost Center", cost_center):
            frappe.get_doc({"doctype": "Cost Center", "cost_center_name": "Main", "company": company, "is_group": 0}).insert(ignore_permissions=True)
            cost_center = frappe.get_last_doc("Cost Center").name
    
    # Ensure types
    for et in ["Travel", "Lodging", "Meals"]:
        if not frappe.db.exists("Expense Claim Type", et):
            frappe.get_doc({"doctype": "Expense Claim Type", "expense_type": et, "accounts": []}).insert(ignore_permissions=True)

    # Claim 1
    claim_desc = "Taksi V2"
    if not frappe.db.exists("Expense Claim", {"description": claim_desc}):
        claim1 = frappe.get_doc({
            "doctype": "Expense Claim",
            "employee": employee,
            "company": company,
            "payable_account": payable_account,
            "posting_date": now_datetime().strftime("%Y-%m-%d"),
            "custom_trip_master": trip.name,
            "expenses": [{
                "expense_type": "Travel",
                "expense_date": now_datetime().strftime("%Y-%m-%d"),
                "amount": 45000,
                "sanctioned_amount": 45000,
                "description": claim_desc,
                "cost_center": cost_center
            }],
            "approval_status": "Approved"
        })
        claim1.insert(ignore_permissions=True)
        claim1.submit()
        print(f"Expense Claim 1 yaratildi: {claim1.name}")

    # 4. GPS Logs
    simulated_points = [
        {"lat": 41.2995, "lng": 69.2401, "activity": "Departure", "time_offset": 0},
        {"lat": 40.9995, "lng": 68.9000, "activity": "Checkpoint", "time_offset": 60},
        {"lat": 39.6542, "lng": 66.9597, "activity": "Arrival", "time_offset": 120},
    ]
    for i, point in enumerate(simulated_points):
        log_time = add_to_date(now_datetime(), minutes=-180 + point["time_offset"])
        if frappe.db.count("Trip Path Log", {"trip_master": trip.name, "activity_type": point["activity"]}) == 0:
            frappe.get_doc({
                "doctype": "Trip Path Log",
                "trip_master": trip.name,
                "employee": employee,
                "timestamp": log_time,
                "latitude": point["lat"],
                "longitude": point["lng"],
                "activity_type": point["activity"],
                "location": str({"type": "Point", "coordinates": [point["lng"], point["lat"]]})
            }).insert(ignore_permissions=True)
            print(f"GPS Log {i+1} yaratildi")

    frappe.db.commit()
    print("--- Muvaffaqiyatli ---")
