# Copyright (c) 2026 Billy Adwar & Moses Njue and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class CasualsAdditionalSalary(Document):
	def validate(self):
		self.set_full_name()

	def set_full_name(self):
		self.full_name = frappe.db.get_value("Casual Staff", self.casual_staff, "full_name")
		return self.full_name

	def validate_payroll_start_date(self):
		# Payroll start date must be at the beginning of the month
		pass

	def validate_component(self):
		"""Component type can only be added once i.e once we have a deduction, we can only 
			have one deduction for the current payroll period
		"""
		pass