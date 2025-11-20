# Copyright (c) 2025, Billy Franklin Adwar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class ProratedSalaryStructureAssignment(Document):

	def on_submit(self):
		self.get_employees_based_on_dates()

	def validate(self):
		self.set_payroll_payable_account()


	@frappe.whitelist(allow_guest=True)
	def get_employees_based_on_dates(self):
		"""
		This method will populate the employees table based on the joining date and the payroll start date
		"""
		if not self.start_date or not self.to_date:
			frappe.throw("Please select both the start date and end date")

		## Cleat the existing table
		self.prorated_employee = []

		employees = frappe.get_all(
			"Employee", 
			fields= ["name","employee_name","ctc","joining_date"],
			filters = {
				"date_of_joining": [">", self.start_date],
				"date_of_joining": ["<=", self.to_date],
				"status": "Active"
			}
		)

		if not employees:
			frappe.msgprint("No employees found in the selected date range")
			return
		
		for emp in employees:
			self.append("prorated_employees",{
				"employee": emp.name,
				"employee_name": emp.employee_name,
				"joining_date": emp.date_of_joining,
				"base_salary": emp.ctc or 0
			})
		frappe.msgprint(f"Added {len(employees)} employees to the prorated list.")
		return True

	def set_payroll_payable_account(self):
		if not self.set_payroll_payable_account:
			payroll_payable_account = frappe.db.get_value(
				"Company", self.company, "default_payroll_payable_account"
			)
			if not payroll_payable_account:
				payroll_payable_account = frappe.db.get_value(
					"Account", 
					{
						"account_name": _("Payroll Payable"), 
						"company": self.company, 
						"account_currency": frappe.db.get_value("Company", self.company, "default_currency"),
						"is_group": 0
					}
				)
