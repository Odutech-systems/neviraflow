# Copyright (c) 2026, Victor Mandela, Billy Adwar & Moses Njue and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, get_datetime

## Have a button action that can be triggered at any time to send an email to users, as an API 
## On click of the button, an email is sent


class GoodsReturnReceipt(Document):
	def before_save(self):
		## Set details on the document before it is saved
		customer, customer_name = self.get_customer_name()
		self.customer = customer
		self.customer_name = customer_name
		sales_person = frappe.db.get_value("Sales Team", {"parent":self.customer, "parenttype":"Customer"}, "sales_person")
		self.sales_person = sales_person
		self.arrival_date = get_datetime()

	def after_insert(self):
		self.send_mail_after_submit()

	def get_customer_name(self):
		## Extract some details and return values
		customer_id = frappe.db.get_value('Delivery Note',self.delivery_note,'customer')
		customer_name = frappe.db.get_value('Delivery Note', self.delivery_note,'customer_name')
		return customer_id, customer_name

	def send_mail_after_submit(self):
		## Send an email to users after submit
		mail_list = ["billy.franks@neviraminerals.com",
			   		"moses.njue@neviraminerals.com",
			   		"sales@neviraminerals.com",
					"fiona@neviraminerals.com",
			   		"jackline.akinyi@neviraminerals.com",
					"steve@neviraminerals.com"]
					
		subject = "ALERT: Potential Credit Note or Inventory Check due to return"
		sender = "systems@neviraminerals.com"

		frappe.sendmail(
			recipients = mail_list,
			sender = sender,
			subject = subject,
			message = f"Please check the return for delivery note https://erp.neviraminerals.com/delivery-note/{self.delivery_note}.\n There is a possible need to create a credit note or material receipt.",
			reference_doctype = self.doctype,
			reference_name = self.name
		)
		
		frappe.db.commit()
		frappe.msgprint("Alert message sent!")