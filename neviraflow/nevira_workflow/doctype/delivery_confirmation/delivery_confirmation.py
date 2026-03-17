# Copyright (c) 2026, Victor Mandela, Billy Adwar & Moses Njue and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class DeliveryConfirmation(Document):
	def before_save(self):
		d_note_id = frappe.db.get_value("Delivery Note",self.delivery_note,'name')
		if not d_note_id:
			frappe.throw(f"Could not find the Delivery Note to link here")

	def on_update(self):
		pass
