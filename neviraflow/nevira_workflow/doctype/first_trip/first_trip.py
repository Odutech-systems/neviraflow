# Copyright (c) 2026 Billy Adwar & Moses Njue and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class FirstTrip(Document):
	def before_save(self):
		self.customer_name = frappe.db.get_value("Customer", self.customer_name, "customer_name")
		self.vehicle_type = frappe.db.get_value("Customer", self.vehicle, "custom_vehicle_ownership")
	
