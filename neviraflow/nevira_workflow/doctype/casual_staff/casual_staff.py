# Copyright (c) 2026 Billy Adwar & Moses Njue and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate, today
from frappe.model.document import Document


class CasualStaff(Document):
	def validate(self):
		self.validate_date()
		self.set_casual_staff_name()
		self.validate_phone()
		self.set_mpesa_phone()
		self.validate_employee_existing()


	def validate_date(self):
		if self.date_of_birth and getdate(self.date_of_birth) > getdate(today()):
			frappe.throw("Date of birth cannot be greater than current date")

	def set_casual_staff_name(self):
		self.full_name = " ".join(
			filter(lambda x: x, [self.first_name, self.middle_name, self.last_name])
		)
	
	def set_mpesa_phone(self):
		self.mpesa_number = self.phone_number

	def validate_phone(self):
		if len(self.phone_number) > 10 or len(self.phone_number) < 10:
			frappe.throw("Phone number should not be less than or more than 10 characters")

	
	def validate_employee_existing(self):
		"""Check if the casual staff we are trying to on board already exists as a general employee."""
		existing_employee = frappe.db.exists("Employee", {
			"national_id": self.national_id
		})
		if existing_employee:
			frappe.throw(f"Casual already exists as an employee, Payroll number {existing_employee}</br>")