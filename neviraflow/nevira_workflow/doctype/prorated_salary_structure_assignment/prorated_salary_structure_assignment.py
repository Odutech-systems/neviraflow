# Copyright (c) 2025, Billy Franklin Adwar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days


class ProratedSalaryStructureAssignment(Document):
	def validate(self):
		self.set_payroll_payable_account()

	def on_submit(self):
		self.create_salary_structure_assignments()

	@frappe.whitelist(allow_guest=True)
	def get_employees_based_on_dates(self):
		"""
		This method will populate the employees table based on the joining date and the payroll start date
		"""
		if not self.start_date or not self.to_date:
			frappe.throw("Please select both the start date and end date")

		## Cleat the existing table
		self.prorated_employees = []

		## get only employees who have joined after the 1st day of the month and before or on the last day of the month
		adjusted_start_date = add_days(self.start_date, 1)
		
		employees = frappe.get_all(
			"Employee", 
			fields= ["name","employee_name","ctc","date_of_joining"],
			filters = {
				"date_of_joining": ["between", [adjusted_start_date, self.to_date]],
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

	
	def create_salary_structure_assignments(self):
		"""
		Create a salary structure assignment for each of the employees in the table
		"""
		assignments_created = []
		
		for employee_row in self.prorated_employees:
			## Check for any existing salary structures in the current month
			existing_assignments = frappe.db.exists(
				"Salary Structure Assignment",{
					"employee": employee_row.employee,
					"salary_structure": self.salary_structure,
					"from_date": employee_row.joining_date,
					"docstatus": 1
				}
			)
			if existing_assignments:
				frappe.msgprint(f"Salary assignment already exists for employee {employee_row.employee_name}")
				continue

			## Create a new salary structure assignment
			assignment_doc = frappe.new_doc("Salary Structure Assignment")
			assignment_doc.update({
				"employee": employee_row.employee,
				"salary_structure": self.salary_structure,
				"from_date": employee_row.joining_date,
				"company": self.company,
				"currency": "KES",
				"base": employee_row.base_salary,
				"income_tax_slab": self.income_tax_slab,
				"payroll_payable_account": self.payroll_payable_account
			})
			
			assignment_doc.insert(ignore_permissions=True)
			assignment_doc.submit()

			employee_row.salary_structure_assignment = assignment_doc.name
			assignments_created.append(assignment_doc.name)

			frappe.db.commit()

		if assignments_created:
			frappe.msgprint(f"Created {len(assignments_created)} Salary structure assignments")
		else:
			frappe.msgprint("No new prorated slary structure created.")
		##self.save()
	
	@frappe.whitelist(allow_guest=True)
	def get_created_assignments(self):
		"""Get a list of created salary structure assignments"""
		assignments = []
		for employee_row in self.prorated_employees:
			if employee_row.name:
				assignments.append(employee_row.name)
		return assignments
	


