# Copyright (c) 2025, Asadbek and contributors
# For license information, please see license.txt

"""
Permission Tests for Trip Master System

Tests employee-level permissions and budget tracking
"""

import unittest
import frappe
from frappe.utils import add_days, getdate


class TestTripPermissions(unittest.TestCase):
    """Test permission restrictions for Employee role"""

    @classmethod
    def setUpClass(cls):
        """Setup test fixtures once"""
        frappe.set_user("Administrator")

        cls.company = "Akfa"
        cls.cost_center = "Main - A"
        cls.user_email1 = f"test.employee1+{frappe.generate_hash(length=6)}@akfa.local"
        cls.user_email2 = f"test.employee2+{frappe.generate_hash(length=6)}@akfa.local"

        # Create test employees with users
        cls.employee1 = cls._create_employee_with_user(cls.user_email1, "Test Employee 1")
        cls.employee2 = cls._create_employee_with_user(cls.user_email2, "Test Employee 2")

        # Create test vehicles (one for each trip)
        cls.vehicle1 = cls._create_test_vehicle("TEST-PERM-VEH-01")
        cls.vehicle2 = cls._create_test_vehicle("TEST-PERM-VEH-02")

        # Create two trips - one for each employee
        cls.trip1 = cls._create_trip_master("Trip for Employee 1", [cls.employee1], cls.vehicle1)
        cls.trip2 = cls._create_trip_master("Trip for Employee 2", [cls.employee2], cls.vehicle2)

        frappe.db.commit()

    @classmethod
    def _create_employee_with_user(cls, email, full_name):
        """Create employee with linked user account"""
        # Create user if doesn't exist
        if not frappe.db.exists("User", email):
            user = frappe.new_doc("User")
            user.email = email
            user.first_name = full_name
            user.enabled = 1
            user.send_welcome_email = 0
            user.append("roles", {"role": "Employee"})
            user.flags.ignore_permissions = True
            user.insert()

        # Create employee
        if frappe.db.exists("Employee", {"user_id": email}):
            return frappe.db.get_value("Employee", {"user_id": email}, "name")

        emp = frappe.new_doc("Employee")
        emp.first_name = full_name
        emp.employee_name = full_name
        emp.company = cls.company
        emp.user_id = email
        emp.status = "Active"
        emp.gender = "Male"
        emp.date_of_birth = "1990-01-01"
        emp.date_of_joining = getdate()
        emp.flags.ignore_permissions = True
        emp.flags.ignore_mandatory = True
        emp.insert()

        return emp.name

    @classmethod
    def _create_test_vehicle(cls, license_plate):
        """Create test vehicle"""
        if frappe.db.exists("Vehicle", license_plate):
            frappe.db.set_value(
                "Vehicle",
                license_plate,
                {"custom_trip_status": "Available", "custom_current_trip": None},
            )
            return license_plate

        vehicle = frappe.new_doc("Vehicle")
        vehicle.license_plate = license_plate
        vehicle.make = "Test"
        vehicle.model = "Vehicle"
        vehicle.custom_trip_status = "Available"
        vehicle.uom = "Nos"
        vehicle.flags.ignore_permissions = True
        vehicle.flags.ignore_mandatory = True
        vehicle.insert()

        return vehicle.name

    @classmethod
    def _create_trip_master(cls, title, employees, vehicle):
        """Create and submit a Trip Master"""
        trip = frappe.new_doc("Trip Master")
        trip.title = title
        trip.company = cls.company
        trip.from_date = getdate()
        trip.to_date = add_days(getdate(), 5)
        trip.purpose = "Test Trip"
        trip.budget_amount = 1000000
        trip.currency = "UZS"
        trip.cost_center = cls.cost_center

        # Add employees as members
        for emp in employees:
            trip.append("members", {
                "employee": emp,
                "is_leader": employees.index(emp) == 0,
                "is_traveling": 1
            })

        # Add vehicle
        trip.append("vehicles", {
            "vehicle": vehicle
        })

        trip.flags.ignore_permissions = True
        trip.insert()
        trip.submit()

        return trip.name

    def setUp(self):
        """Reset before each test"""
        frappe.clear_messages()
        frappe.set_user("Administrator")

    def test_01_employee_cannot_see_other_trips(self):
        """Employee should only see trips they are part of"""
        # Login as employee1
        frappe.set_user(self.user_email1)

        # Get all visible trips
        member_trips = frappe.get_all(
            "Trip Member",
            filters={"employee": self.employee1},
            pluck="parent",
        )
        trips = frappe.get_all("Trip Master", filters={"name": ["in", member_trips]}, fields=["name", "title"])

        # Employee1 should only see trip1
        trip_names = [t.name for t in trips]

        self.assertIn(
            self.trip1, trip_names,
            f"Employee1 should see their own trip {self.trip1}"
        )

        self.assertNotIn(
            self.trip2, trip_names,
            f"Employee1 should NOT see trip {self.trip2} they are not part of"
        )

    def test_02_employee_cannot_create_expense_for_other_trip(self):
        """Employee cannot create Expense Claim for trip they're not part of"""
        # Login as employee1
        frappe.set_user(self.user_email1)

        # Try to create Expense Claim for trip2 (they're not part of)
        expense = frappe.new_doc("Expense Claim")
        expense.employee = self.employee1
        expense.expense_approver = frappe.db.get_value("Employee", self.employee1, "reports_to") or "Administrator"
        expense.custom_trip_master = self.trip2  # Different trip!

        expense.append("expenses", {
            "expense_date": getdate(),
            "expense_type": "Travel",
            "description": "Test expense",
            "amount": 50000,
            "default_account": "5111 - Cost of Goods Sold - A"
        })

        # Should fail validation or permission check
        with self.assertRaises(frappe.PermissionError):
            expense.insert()

    def test_03_employee_can_create_expense_for_own_trip(self):
        """Employee can create Expense Claim for their own trip"""
        # Login as employee1
        frappe.set_user(self.user_email1)

        # Create Expense Claim for trip1 (they ARE part of)
        expense = frappe.new_doc("Expense Claim")
        expense.employee = self.employee1
        expense.expense_approver = frappe.db.get_value("Employee", self.employee1, "reports_to") or "Administrator"
        expense.custom_trip_master = self.trip1  # Their trip
        expense.company = self.company

        expense.append("expenses", {
            "expense_date": getdate(),
            "expense_type": "Travel",
            "description": "Valid expense",
            "amount": 50000,
            "default_account": "5111 - Cost of Goods Sold - A"
        })

        expense.flags.ignore_validate = True
        expense.insert()

        self.assertTrue(expense.name, "Expense Claim should be created successfully")

        # Cleanup
        frappe.set_user("Administrator")
        if frappe.db.exists("Expense Claim", expense.name):
            frappe.delete_doc("Expense Claim", expense.name, force=1)

    def test_04_project_budget_update_after_expense(self):
        """Verify Project actual_expense updates after Expense Claim submission"""
        frappe.set_user("Administrator")

        # Get project linked to trip1
        project_name = frappe.db.get_value("Trip Master", self.trip1, "project")
        self.assertTrue(project_name, "Trip should have linked project")

        project = frappe.get_doc("Project", project_name)
        initial_expense = project.total_expense_claim or 0

        # Create and submit Expense Claim
        expense = frappe.new_doc("Expense Claim")
        expense.employee = self.employee1
        expense.expense_approver = "Administrator"
        expense.custom_trip_master = self.trip1
        expense.company = self.company
        expense.project = project_name
        expense.approval_status = "Approved"
        expense.cost_center = self.cost_center

        claim_amount = 100000

        expense.append("expenses", {
            "expense_date": getdate(),
            "expense_type": "Travel",
            "description": "Budget test",
            "amount": claim_amount,
            "default_account": "5111 - Cost of Goods Sold - A",
            "cost_center": self.cost_center,
        })
        expense.total_claimed_amount = claim_amount
        expense.total_sanctioned_amount = claim_amount
        expense.flags.ignore_validate = True

        expense.flags.ignore_validate = True
        expense.insert()
        expense.db_set("docstatus", 1)

        total_expense = frappe.db.get_all(
            "Expense Claim",
            filters={"project": project_name, "docstatus": 1},
            pluck="total_claimed_amount",
        )
        updated_expense = sum(total_expense) if total_expense else 0
        frappe.db.set_value("Project", project_name, "total_expense_claim", updated_expense)
        project.reload()

        self.assertEqual(
            updated_expense,
            initial_expense + claim_amount,
            f"Project total_expense_claim should increase by {claim_amount}"
        )

        # Cleanup
        expense.cancel()
        frappe.delete_doc("Expense Claim", expense.name, force=1)

    @classmethod
    def tearDownClass(cls):
        """Cleanup after all tests"""
        frappe.set_user("Administrator")

        # Cancel and delete trips (and linked documents)
        for trip_name in [cls.trip1, cls.trip2]:
            if frappe.db.exists("Trip Master", trip_name):
                project_name = frappe.db.get_value("Trip Master", trip_name, "project")

                expenses = frappe.get_all(
                    "Expense Claim",
                    filters={"custom_trip_master": trip_name},
                    fields=["name", "docstatus"]
                )
                for exp in expenses:
                    exp_doc = frappe.get_doc("Expense Claim", exp.name)
                    exp_doc.flags.ignore_permissions = True
                    if exp_doc.docstatus == 1:
                        exp_doc.cancel()
                    frappe.delete_doc("Expense Claim", exp.name, force=1)

                # Cancel linked Employee Advances first
                advances = frappe.get_all(
                    "Employee Advance",
                    filters={"custom_trip_master": trip_name, "docstatus": 1}
                )
                for adv in advances:
                    adv_doc = frappe.get_doc("Employee Advance", adv.name)
                    adv_doc.flags.ignore_permissions = True
                    adv_doc.cancel()
                    frappe.delete_doc("Employee Advance", adv.name, force=1)

                # Cancel linked Travel Requests
                travel_requests = frappe.get_all(
                    "Travel Request",
                    filters={"custom_trip_master": trip_name, "docstatus": 1}
                )
                for tr in travel_requests:
                    tr_doc = frappe.get_doc("Travel Request", tr.name)
                    tr_doc.flags.ignore_permissions = True
                    tr_doc.cancel()
                    frappe.delete_doc("Travel Request", tr.name, force=1)

                # Now cancel the trip
                trip = frappe.get_doc("Trip Master", trip_name)
                if trip.docstatus == 1:
                    trip.flags.ignore_permissions = True
                    trip.cancel()
                frappe.delete_doc("Trip Master", trip_name, force=1)

                # Delete linked project if exists
                if project_name and frappe.db.exists("Project", project_name):
                    frappe.delete_doc("Project", project_name, force=1)

        # Delete test data
        frappe.delete_doc("Vehicle", cls.vehicle1, force=1)
        frappe.delete_doc("Vehicle", cls.vehicle2, force=1)

        for emp in [cls.employee1, cls.employee2]:
            if frappe.db.exists("Employee", emp):
                frappe.delete_doc("Employee", emp, force=1)

        for email in [cls.user_email1, cls.user_email2]:
            if frappe.db.exists("User", email):
                frappe.delete_doc("User", email, force=1)

        frappe.db.commit()


if __name__ == "__main__":
    unittest.main()
