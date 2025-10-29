# Copyright (c) 2025, Victor Mandela and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, today


class EmployeeAdditionalDeduction(Document):
	def before_insert(self):
		self.employee_name = frappe.db.get_value("Employee",self.employee, "employee_name")

	def validate(self):
		if getdate(self.from_date) > getdate(self.to_date):
			raise frappe.throw(f"From date cannot be greater than To date: Please change to a lower From date {self.from_date}")
		
		self.validate_status()

	def validate_status(self):
		current_date = today()
		if getdate(current_date) > getdate(self.to_date):
			self.status = "Closed"

