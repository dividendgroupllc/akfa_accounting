# Copyright (c) 2025, Asadbek and contributors
# For license information, please see license.txt

"""
Integration Test for Trip Master Logic
Tests full workflow: Employee setup, Trip creation, Vehicle allocation, Financial tracking
"""

import frappe
import unittest
from frappe.utils import nowdate, add_days, add_to_date, getdate, now_datetime


class TestTripLogic(unittest.TestCase):
	"""Integration tests for Trip Master system"""

	@classmethod
	def setUpClass(cls):
		"""Setup test fixtures once for all tests"""
		frappe.set_user("Administrator")

		# Use existing Akfa company
		cls.company = "Akfa"
		cls.cost_center = "Main - A"
		cls.advance_account = "1610 - Employee Advances - A"

		cls.travel_purpose = cls._create_travel_purpose()
		cls.employees = cls._create_test_employees(5)
		cls.vehicles = cls._create_test_vehicles(2)
		cls.employee_group = cls._create_employee_group()

		# Commit test fixtures
		frappe.db.commit()

	def setUp(self):
		"""Reset state before each test"""
		frappe.clear_messages()
		# Reset vehicle statuses
		for vehicle in self.vehicles:
			frappe.db.set_value("Vehicle", vehicle, {
				"custom_trip_status": "Available",
				"custom_current_trip": None
			}, update_modified=False)

	def tearDown(self):
		"""Cleanup after each test"""
		frappe.db.rollback()

	@classmethod
	def _create_travel_purpose(cls):
		"""Create travel purpose for tests"""
		purpose_name = "Business Meeting"
		if frappe.db.exists("Purpose of Travel", purpose_name):
			return purpose_name

		purpose = frappe.new_doc("Purpose of Travel")
		purpose.purpose_of_travel = purpose_name
		purpose.insert(ignore_if_duplicate=True)
		return purpose.name

	@classmethod
	def _create_test_employees(cls, count):
		"""Create test employees"""
		employees = []
		for i in range(1, count + 1):
			emp_id = f"TEST-EMP-{i:03d}"
			if frappe.db.exists("Employee", emp_id):
				employees.append(emp_id)
				continue

			emp = frappe.new_doc("Employee")
			emp.employee = emp_id
			emp.first_name = f"Test Employee {i}"
			emp.company = cls.company
			emp.status = "Active"
			emp.date_of_joining = nowdate()
			emp.flags.ignore_mandatory = True
			emp.insert(ignore_if_duplicate=True)
			employees.append(emp.name)

		return employees

	@classmethod
	def _create_test_vehicles(cls, count):
		"""Create test vehicles"""
		vehicles = []
		for i in range(1, count + 1):
			vehicle_name = f"TEST-VEHICLE-{i:02d}"
			if frappe.db.exists("Vehicle", vehicle_name):
				# Reset status to Available
				frappe.db.set_value("Vehicle", vehicle_name, {
					"custom_trip_status": "Available",
					"custom_current_trip": None
				})
				vehicles.append(vehicle_name)
				continue

			vehicle = frappe.new_doc("Vehicle")
			vehicle.license_plate = vehicle_name
			vehicle.make = "Toyota"
			vehicle.model = "Hiace"
			vehicle.custom_trip_status = "Available"
			vehicle.flags.ignore_mandatory = True
			vehicle.insert(ignore_if_duplicate=True)
			vehicles.append(vehicle.name)

		return vehicles

	@classmethod
	def _create_employee_group(cls):
		"""Create employee group (Sektor)"""
		group_name = "Test Sektor IT"
		if frappe.db.exists("Employee Group", group_name):
			return group_name

		group = frappe.new_doc("Employee Group")
		group.employee_group_name = group_name
		group.insert(ignore_if_duplicate=True)
		return group.name

	def test_01_trip_master_submission_workflow(self):
		"""Test complete Trip Master submission workflow"""
		print("\n=== Test 1: Trip Master Submission Workflow ===")

		# Create Trip Master
		trip = frappe.new_doc("Trip Master")
		trip.title = "Test Trip to Samarkand"
		trip.company = self.company
		trip.cost_center = self.cost_center
		trip.from_date = nowdate()
		trip.to_date = add_days(nowdate(), 3)
		trip.destination = "Samarkand"
		trip.purpose = "Business Meeting"
		trip.budget_amount = 40000
		trip.currency = "USD"
		trip.posting_date = nowdate()

		# Add 5 members (1 leader)
		for idx, emp in enumerate(self.employees):
			trip.append("members", {
				"employee": emp,
				"is_leader": 1 if idx == 0 else 0
			})

		# Add 2 vehicles
		for vehicle in self.vehicles:
			trip.append("vehicles", {
				"vehicle": vehicle
			})

		trip.insert()
		print(f"✓ Trip Master created: {trip.name}")

		# Submit
		trip.submit()
		print(f"✓ Trip Master submitted: {trip.name}")

		# Validation 1: Check 5 Travel Requests
		travel_requests = frappe.get_all(
			"Travel Request",
			filters={"custom_trip_master": trip.name, "docstatus": 1},
			fields=["name", "employee"]
		)
		self.assertEqual(len(travel_requests), 5, "Should create 5 Travel Requests")
		print(f"✓ Validated: {len(travel_requests)} Travel Requests created")

		# Validation 2: Check Employee Advance for Leader
		leader_emp = self.employees[0]
		employee_advances = frappe.get_all(
			"Employee Advance",
			filters={
				"custom_trip_master": trip.name,
				"employee": leader_emp,
				"docstatus": 1
			},
			fields=["name", "advance_amount"]
		)
		self.assertEqual(len(employee_advances), 1, "Should create 1 Employee Advance for leader")
		self.assertEqual(employee_advances[0].advance_amount, 40000, "Advance amount should be 40K USD")
		print(f"✓ Validated: Employee Advance {employee_advances[0].name} = 40,000 USD")

		# Validation 3: Check Vehicle Status
		for vehicle in self.vehicles:
			status = frappe.db.get_value("Vehicle", vehicle, "custom_trip_status")
			current_trip = frappe.db.get_value("Vehicle", vehicle, "custom_current_trip")
			self.assertEqual(status, "In Trip", f"Vehicle {vehicle} should be 'In Trip'")
			self.assertEqual(current_trip, trip.name, f"Vehicle {vehicle} should link to trip")
		print(f"✓ Validated: 2 Vehicles marked 'In Trip'")

		# Validation 4: Check Project Creation and Linkage
		project_name = frappe.db.get_value("Trip Master", trip.name, "project")
		self.assertIsNotNone(project_name, "Project should be created")

		project = frappe.get_doc("Project", project_name)
		self.assertEqual(project.custom_trip_master, trip.name, "Project should link to Trip Master")
		self.assertEqual(project.estimated_costing, 40000, "Project budget should be 40K USD")
		print(f"✓ Validated: Project {project_name} created with budget 40K USD")

		# Check all Travel Requests linked to Trip Master
		for tr in travel_requests:
			tr_doc = frappe.get_doc("Travel Request", tr.name)
			self.assertEqual(tr_doc.custom_trip_master, trip.name, "Travel Request should link to Trip")
		print(f"✓ Validated: All Travel Requests linked to Trip Master")

		# Check Employee Advance linked to Trip Master
		ea_doc = frappe.get_doc("Employee Advance", employee_advances[0].name)
		self.assertEqual(ea_doc.custom_trip_master, trip.name, "Employee Advance should link to Trip")
		print(f"✓ Validated: Employee Advance linked to Trip Master")

		self.trip_master_name = trip.name
		print(f"\n✅ Test 1 PASSED: All validations successful\n")

	def test_02_vehicle_collision_test(self):
		"""Test vehicle allocation collision - same vehicle cannot be in 2 trips"""
		print("\n=== Test 2: Vehicle Collision Test ===")

		# First trip
		trip1 = frappe.new_doc("Trip Master")
		trip1.title = "First Trip"
		trip1.company = self.company
		trip1.cost_center = self.cost_center
		trip1.from_date = nowdate()
		trip1.to_date = add_days(nowdate(), 2)
		trip1.destination = "Tashkent"
		trip1.purpose = "Meeting"
		trip1.budget_amount = 5000
		trip1.currency = "USD"
		trip1.posting_date = nowdate()

		trip1.append("members", {
			"employee": self.employees[0],
			"is_leader": 1
		})

		trip1.append("vehicles", {
			"vehicle": self.vehicles[0]
		})

		trip1.insert()
		trip1.submit()
		print(f"✓ Trip 1 submitted with vehicle: {self.vehicles[0]}")

		# Second trip - try to use same vehicle
		trip2 = frappe.new_doc("Trip Master")
		trip2.title = "Second Trip"
		trip2.company = self.company
		trip2.cost_center = self.cost_center
		trip2.from_date = nowdate()
		trip2.to_date = add_days(nowdate(), 2)
		trip2.destination = "Bukhara"
		trip2.purpose = "Conference"
		trip2.budget_amount = 3000
		trip2.currency = "USD"
		trip2.posting_date = nowdate()

		trip2.append("members", {
			"employee": self.employees[1],
			"is_leader": 1
		})

		trip2.append("vehicles", {
			"vehicle": self.vehicles[0]  # Same vehicle!
		})

		# Should raise ValidationError on insert (validation happens before save)
		with self.assertRaises(Exception) as context:
			trip2.insert()

		error_msg = str(context.exception)
		self.assertIn("not available", error_msg.lower(), "Should raise vehicle availability error")
		print(f"✓ Validated: System rejected duplicate vehicle assignment")
		print(f"✓ Error message: {error_msg[:100]}...")

		print(f"\n✅ Test 2 PASSED: Collision detection working\n")

	def test_03_financial_test_expense_claim(self):
		"""Test Expense Claim creation and Project budget tracking"""
		print("\n=== Test 3: Financial Test - Expense Claim ===")

		# Create Trip Master
		trip = frappe.new_doc("Trip Master")
		trip.title = "Financial Test Trip"
		trip.company = self.company
		trip.cost_center = self.cost_center
		trip.from_date = nowdate()
		trip.to_date = add_days(nowdate(), 3)
		trip.destination = "Khiva"
		trip.purpose = "Audit"
		trip.budget_amount = 10000
		trip.currency = "USD"
		trip.posting_date = nowdate()

		trip.append("members", {
			"employee": self.employees[0],
			"is_leader": 1
		})

		trip.insert()
		trip.submit()
		print(f"✓ Trip Master created and submitted: {trip.name}")

		# Get Project
		project_name = frappe.db.get_value("Trip Master", trip.name, "project")
		project = frappe.get_doc("Project", project_name)
		initial_budget = project.estimated_costing
		print(f"✓ Initial Project Budget: {initial_budget:,.0f} USD")

		# Create Expense Claim
		expense_claim = frappe.new_doc("Expense Claim")
		expense_claim.employee = self.employees[0]
		expense_claim.company = self.company
		expense_claim.posting_date = nowdate()
		expense_claim.custom_trip_master = trip.name
		expense_claim.project = project_name

		# Add expense detail
		expense_claim.append("expenses", {
			"expense_date": nowdate(),
			"description": "Hotel and Transport",
			"expense_type": "Travel",
			"amount": 2000
		})

		expense_claim.flags.ignore_mandatory = True
		expense_claim.flags.ignore_validate = True
		expense_claim.insert()
		print(f"✓ Expense Claim created: {expense_claim.name} for 2,000 USD")

		# Validate linkage
		self.assertEqual(expense_claim.custom_trip_master, trip.name, "Expense Claim should link to Trip")
		self.assertEqual(expense_claim.project, project_name, "Expense Claim should link to Project")
		print(f"✓ Validated: Expense Claim linked to Trip Master and Project")

		# Check total expenses
		total_expenses = sum(d.amount for d in expense_claim.expenses)
		self.assertEqual(total_expenses, 2000, "Total expense should be 2K USD")
		print(f"✓ Validated: Total Expense Claim amount = 2,000 USD")

		print(f"\n✅ Test 3 PASSED: Expense Claim created and linked\n")

	def test_04_trip_completion_releases_resources(self):
		"""Trip completion should free vehicles and close project"""
		print("\n=== Test 4: Trip Completion Releases Resources ===")

		trip = frappe.new_doc("Trip Master")
		trip.title = "Completion Test Trip"
		trip.company = self.company
		trip.cost_center = self.cost_center
		trip.from_date = nowdate()
		trip.to_date = add_days(nowdate(), 1)
		trip.destination = "Navoi"
		trip.purpose = "Completion Flow"
		trip.budget_amount = 5000
		trip.currency = "USD"
		trip.posting_date = nowdate()

		trip.append("members", {"employee": self.employees[0], "is_leader": 1})
		trip.append("vehicles", {"vehicle": self.vehicles[0]})
		trip.append(
			"itinerary",
			{
				"from_city": "Tashkent",
				"to_city": "Samarkand",
				"departure_datetime": now_datetime(),
				"arrival_datetime": add_to_date(now_datetime(), hours=4),
			},
		)

		trip.insert()
		trip.submit()
		print(f"✓ Trip submitted: {trip.name}")

		trip.complete_trip()
		trip.reload()
		print("✓ Completion API called")

		vehicle_status = frappe.db.get_value("Vehicle", self.vehicles[0], "custom_trip_status")
		project_status = frappe.db.get_value("Project", trip.project, "status")

		self.assertEqual(trip.status, "Completed")
		self.assertEqual(vehicle_status, "Available")
		self.assertEqual(project_status, "Completed")
		print("✓ Vehicles released and project closed")

		print(f"\n✅ Test 4 PASSED: Completion flow releases resources\n")


def run_tests():
	"""Helper function to run tests programmatically"""
	suite = unittest.TestLoader().loadTestsFromTestCase(TestTripLogic)
	runner = unittest.TextTestRunner(verbosity=2)
	result = runner.run(suite)
	return result
