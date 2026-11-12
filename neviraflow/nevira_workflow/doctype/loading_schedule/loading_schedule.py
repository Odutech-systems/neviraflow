# Copyright (c) 2026, Victor Mandela, Billy Adwar & Moses Njue and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
import frappe

class LoadingSchedule(Document):
	def before_save(self):
		self.prepared_by = frappe.session.user
		self.logistics_manager_name = frappe.get_value("Employee", self.logistics_manager, "employee_name")


