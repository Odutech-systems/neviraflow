# Copyright (c) 2026 Billy Adwar & Moses Njue and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class CasualsAdditionalSalary(Document):
	def validate(self):
		self.set_full_name()

	def set_full_name(self):
		self.full_name = frappe.db.get_value("Casual Staff", self.casual_staff, "full_name")
