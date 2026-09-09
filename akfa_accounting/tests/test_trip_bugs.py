# Copyright (c) 2025, Asadbek and contributors
# For license information, please see license.txt

"""
Regression tests for Trip Master defects.

Each test here reproduces a concrete bug found during the September 2026 audit:
link persistence on submit, cancellation of provisioned documents, role-based
creation, and permission checks on the whitelisted mobile/monitoring APIs.
"""

import unittest

import frappe
from frappe.utils import add_days, getdate, nowdate


class TripFixtureMixin:
	"""Shared fixtures: company, employees, vehicles, trips."""

	company = "Akfa"
	cost_center = "Main - A"

	@classmethod
	def _employee(cls, key, user_email=None, roles=None):
		# Employee is named by series, so look the fixture up by its stable fields
		full_name = f"Bug Test {key}"
		existing = frappe.db.get_value(
			"Employee", {"user_id": user_email} if user_email else {"first_name": full_name}, "name"
		)
		if existing:
			return existing

		if user_email and not frappe.db.exists("User", user_email):
			user = frappe.new_doc("User")
			user.email = user_email
			user.first_name = f"Bug Test {key}"
			user.enabled = 1
			user.send_welcome_email = 0
			for role in roles or ["Employee"]:
				user.append("roles", {"role": role})
			user.flags.ignore_permissions = True
			user.insert()

		emp = frappe.new_doc("Employee")
		emp.first_name = full_name
		emp.company = cls.company
		emp.status = "Active"
		emp.date_of_joining = nowdate()
		if user_email:
			emp.user_id = user_email
		emp.flags.ignore_mandatory = True
		emp.flags.ignore_permissions = True
		emp.insert(ignore_if_duplicate=True)
		return emp.name

	@classmethod
	def _vehicle(cls, key):
		plate = f"BUG-VEH-{key}"
		if frappe.db.exists("Vehicle", plate):
			frappe.db.set_value(
				"Vehicle", plate, {"custom_trip_status": "Available", "custom_current_trip": None}
			)
			return plate

		vehicle = frappe.new_doc("Vehicle")
		vehicle.license_plate = plate
		vehicle.make = "Toyota"
		vehicle.model = "Hiace"
		vehicle.custom_trip_status = "Available"
		vehicle.flags.ignore_mandatory = True
		vehicle.flags.ignore_permissions = True
		vehicle.insert(ignore_if_duplicate=True)
		return vehicle.name

	def _make_trip(self, members, vehicles=None, budget=1000000, submit=True):
		trip = frappe.new_doc("Trip Master")
		trip.title = f"Bug Trip {frappe.generate_hash(length=6)}"
		trip.company = self.company
		trip.cost_center = self.cost_center
		trip.posting_date = nowdate()
		trip.from_date = getdate()
		trip.to_date = add_days(getdate(), 3)
		trip.destination = "Samarkand"
		trip.purpose = "Regression test"
		trip.budget_amount = budget
		trip.currency = "UZS"

		for idx, emp in enumerate(members):
			trip.append("members", {"employee": emp, "is_leader": 1 if idx == 0 else 0})
		for vehicle in vehicles or []:
			trip.append("vehicles", {"vehicle": vehicle})

		trip.insert()
		if submit:
			trip.submit()
		return trip


class TestTripLinkPersistence(TripFixtureMixin, unittest.TestCase):
	"""Links written during on_submit must survive to the database."""

	@classmethod
	def setUpClass(cls):
		frappe.set_user("Administrator")
		cls.leader = cls._employee("L1")
		cls.member = cls._employee("M1")
		cls.vehicle = cls._vehicle("01")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_travel_request_link_is_persisted(self):
		"""Trip Member.travel_request must be readable after reload."""
		trip = self._make_trip([self.leader, self.member], [self.vehicle])

		reloaded = frappe.get_doc("Trip Master", trip.name)
		for row in reloaded.members:
			self.assertTrue(
				row.travel_request,
				f"Trip Member {row.employee} has no travel_request stored in the database",
			)

	def test_employee_advance_link_is_persisted(self):
		"""Trip Member.employee_advance must be readable after reload for the leader."""
		trip = self._make_trip([self.leader, self.member])

		reloaded = frappe.get_doc("Trip Master", trip.name)
		leader_row = next(row for row in reloaded.members if row.is_leader)
		self.assertTrue(
			leader_row.employee_advance,
			"Leader row has no employee_advance stored in the database",
		)

	def test_cancel_cancels_travel_requests(self):
		"""Cancelling the trip must cancel every provisioned Travel Request."""
		trip = self._make_trip([self.leader, self.member])
		requests = frappe.get_all(
			"Travel Request", filters={"custom_trip_master": trip.name}, pluck="name"
		)
		self.assertTrue(requests, "no Travel Requests were provisioned")

		frappe.get_doc("Trip Master", trip.name).cancel()

		for name in requests:
			self.assertEqual(
				frappe.db.get_value("Travel Request", name, "docstatus"),
				2,
				f"Travel Request {name} was left submitted after the trip was cancelled",
			)

	def test_cancel_cancels_employee_advance(self):
		"""Cancelling the trip must cancel the leader's Employee Advance."""
		trip = self._make_trip([self.leader, self.member])
		advances = frappe.get_all(
			"Employee Advance", filters={"custom_trip_master": trip.name}, pluck="name"
		)
		self.assertTrue(advances, "no Employee Advance was provisioned")

		frappe.get_doc("Trip Master", trip.name).cancel()

		for name in advances:
			self.assertEqual(
				frappe.db.get_value("Employee Advance", name, "docstatus"),
				2,
				f"Employee Advance {name} was left submitted after the trip was cancelled",
			)


class TestTripApiPermissions(TripFixtureMixin, unittest.TestCase):
	"""Whitelisted trip APIs must not leak data across employees."""

	@classmethod
	def setUpClass(cls):
		frappe.set_user("Administrator")
		cls.insider = cls._employee("IN", "bug.insider@akfa.local")
		cls.outsider = cls._employee("OUT", "bug.outsider@akfa.local")
		# a colleague, so trips under test carry more than one Employee link
		cls.colleague = cls._employee("COL")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_member_can_open_multi_member_trip(self):
		"""HRMS auto-creates a User Permission per Employee; other members' rows
		must not hide the whole trip from someone who is on it."""
		trip = self._make_trip([self.insider, self.colleague])

		frappe.set_user("bug.insider@akfa.local")
		self.assertTrue(
			frappe.has_permission("Trip Master", "read", trip.name),
			"a trip member cannot read a trip that has other members on it",
		)

	def test_get_trip_path_denies_outsider(self):
		"""An employee outside the trip must not read its GPS trail."""
		from akfa_accounting.api import get_trip_path

		trip = self._make_trip([self.insider, self.colleague])
		log = frappe.new_doc("Trip Path Log")
		log.trip_master = trip.name
		log.employee = self.insider
		log.timestamp = frappe.utils.now_datetime()
		log.latitude = 41.3
		log.longitude = 69.24
		log.flags.ignore_permissions = True
		log.insert()

		frappe.set_user("bug.outsider@akfa.local")
		with self.assertRaises(frappe.PermissionError):
			get_trip_path(trip.name)

	def test_get_trip_balance_denies_outsider(self):
		"""An employee outside the trip must not read its budget."""
		from akfa_accounting.api import get_trip_balance

		trip = self._make_trip([self.insider, self.colleague])

		frappe.set_user("bug.outsider@akfa.local")
		with self.assertRaises(frappe.PermissionError):
			get_trip_balance(trip.name)

	def test_get_trip_path_allows_member(self):
		"""A trip member must still be able to read the trail."""
		from akfa_accounting.api import get_trip_path

		trip = self._make_trip([self.insider, self.colleague])

		frappe.set_user("bug.insider@akfa.local")
		self.assertIsInstance(get_trip_path(trip.name), list)

	def test_check_in_logs_own_location(self):
		"""The mobile check-in API must accept a member logging their own position."""
		from akfa_accounting.api import log_trip_path

		trip = self._make_trip([self.insider, self.colleague])

		frappe.set_user("bug.insider@akfa.local")
		result = log_trip_path(trip.name, self.insider, 41.3, 69.24, "Checkpoint")
		self.assertTrue(result["success"])
		self.assertEqual(
			frappe.db.get_value("Trip Path Log", result["log_id"], "employee"), self.insider
		)

	def test_check_in_rejects_spoofed_employee(self):
		"""The mobile check-in API must refuse logging on another employee's behalf."""
		from akfa_accounting.api import log_trip_path

		trip = self._make_trip([self.insider])

		frappe.set_user("bug.outsider@akfa.local")
		with self.assertRaises(frappe.PermissionError):
			log_trip_path(trip.name, self.insider, 41.3, 69.24, "Checkpoint")


class TestTripCreationPermission(TripFixtureMixin, unittest.TestCase):
	"""HR User holds `create` on the doctype and must be able to use it."""

	@classmethod
	def setUpClass(cls):
		frappe.set_user("Administrator")
		cls.hr_user = "bug.hruser@akfa.local"
		cls.member = cls._employee("HRM")
		if not frappe.db.exists("User", cls.hr_user):
			user = frappe.new_doc("User")
			user.email = cls.hr_user
			user.first_name = "Bug HR User"
			user.enabled = 1
			user.send_welcome_email = 0
			user.append("roles", {"role": "HR User"})
			user.append("roles", {"role": "Employee"})
			user.flags.ignore_permissions = True
			user.insert()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_hr_user_can_create_trip(self):
		"""Creating a draft Trip Master must not raise PermissionError for HR User."""
		frappe.set_user(self.hr_user)

		trip = frappe.new_doc("Trip Master")
		trip.title = "HR User draft"
		trip.company = self.company
		trip.cost_center = self.cost_center
		trip.posting_date = nowdate()
		trip.from_date = getdate()
		trip.to_date = add_days(getdate(), 1)
		trip.purpose = "HR User creation check"
		trip.append("members", {"employee": self.member, "is_leader": 1})

		trip.insert()
		self.assertTrue(frappe.db.exists("Trip Master", trip.name))


class TestExpenseClaimTripGuard(TripFixtureMixin, unittest.TestCase):
	"""An employee must not book expenses against a trip they are not on."""

	@classmethod
	def setUpClass(cls):
		frappe.set_user("Administrator")
		cls.insider = cls._employee("ECI")
		cls.outsider = cls._employee("ECO", "bug.outsider2@akfa.local")
		cls.claimer = cls._employee("ECC", "bug.claimer@akfa.local")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def _claim(self, employee, trip_name):
		claim = frappe.new_doc("Expense Claim")
		claim.employee = employee
		claim.company = self.company
		claim.posting_date = nowdate()
		claim.custom_trip_master = trip_name
		claim.payable_account = "Creditors - A"
		claim.cost_center = self.cost_center
		claim.append(
			"expenses",
			{
				"expense_date": nowdate(),
				"expense_type": "Travel",
				"description": "Hotel",
				"amount": 100000,
				"sanctioned_amount": 100000,
				"cost_center": self.cost_center,
			},
		)
		return claim

	def test_mobile_expense_works_while_advance_is_unpaid(self):
		"""The leader holds an Employee Advance that stays Unpaid until finance pays it.
		Allocating against it would violate HRMS's unclaimed-amount rule, so the claim
		must fall back to a plain reimbursement instead of failing."""
		from akfa_accounting.mobile_api.expense_claim import create_expense_from_mobile

		trip = self._make_trip([self.claimer, self.insider])
		advance = frappe.get_all(
			"Employee Advance",
			filters={"custom_trip_master": trip.name},
			fields=["name", "status", "paid_amount"],
		)
		self.assertEqual(advance[0].status, "Unpaid", "fixture expects an unpaid advance")

		frappe.set_user("bug.claimer@akfa.local")
		result = create_expense_from_mobile(trip.name, "Others", 120000, "Hotel")

		self.assertTrue(result["success"])
		self.assertFalse(
			result["advance_used"], "an unpaid advance must not be allocated against"
		)

	def test_mobile_expense_uses_a_paid_advance(self):
		"""Once finance pays the advance, the claim must draw from it."""
		from akfa_accounting.events.employee_advance import create_payment_entry_for_advance
		from akfa_accounting.mobile_api.expense_claim import create_expense_from_mobile

		trip = self._make_trip([self.claimer, self.insider])
		advance_name = frappe.get_all(
			"Employee Advance", filters={"custom_trip_master": trip.name}, pluck="name"
		)[0]

		create_payment_entry_for_advance(frappe.get_doc("Employee Advance", advance_name))
		advance = frappe.get_doc("Employee Advance", advance_name)
		self.assertGreater(advance.paid_amount, 0, "advance was not paid by the helper")

		frappe.set_user("bug.claimer@akfa.local")
		result = create_expense_from_mobile(trip.name, "Others", 120000, "Hotel")

		self.assertTrue(result["success"])
		self.assertTrue(result["advance_used"], "a paid advance must be allocated against")

	def test_employee_cannot_claim_on_behalf_of_another(self):
		"""Naming a different employee must not bypass the trip membership guard."""
		trip = self._make_trip([self.insider])

		frappe.set_user("bug.outsider2@akfa.local")
		claim = self._claim(self.insider, trip.name)
		with self.assertRaises(frappe.PermissionError):
			claim.insert(ignore_permissions=True)
