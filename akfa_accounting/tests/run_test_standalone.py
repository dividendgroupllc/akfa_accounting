#!/usr/bin/env python3
# Copyright (c) 2025, Asadbek and contributors
# For license information, please see license.txt

"""
Standalone test runner for Trip Master integration tests
Run with: bench --site akfa.local execute akfa_accounting.tests.run_test_standalone.main
"""

import frappe


def main():
	"""Run Trip Master integration tests"""
	print("\n" + "="*70)
	print("Trip Master Integration Test Suite")
	print("="*70 + "\n")

	# Import test module
	from akfa_accounting.tests.test_trip_logic import run_tests

	# Run tests
	result = run_tests()

	# Print summary
	print("\n" + "="*70)
	print("Test Summary")
	print("="*70)
	print(f"Tests run: {result.testsRun}")
	print(f"Failures: {len(result.failures)}")
	print(f"Errors: {len(result.errors)}")
	print(f"Success: {result.wasSuccessful()}")
	print("="*70 + "\n")

	return result.wasSuccessful()


if __name__ == "__main__":
	main()
