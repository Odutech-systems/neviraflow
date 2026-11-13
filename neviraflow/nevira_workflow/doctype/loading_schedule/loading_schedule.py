# Copyright (c) 2026, Victor Mandela, Billy Adwar & Moses Njue and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
import frappe
from frappe.utils import getdate, today

class LoadingSchedule(Document):

	def validate(self):
		self.validate_date()

	def validate_date(self):
		if getdate(self.loading_date) != getdate(today()):
			frappe.throw("Loading date cannot be a day in future or in the past.")

	def before_save(self):
		self.prepared_by = frappe.session.user
		self.logistics_manager_name = frappe.get_value("Employee", self.logistics_manager, "employee_name")

		for row in self.first_trip:
			row.customer_name = frappe.db.get_value("Customer", row.customer, "customer_name")
			
		for row in self.second_trip:
			row.customer_name = frappe.db.get_value("Customer", row.customer, "customer_name")

		for row in self.after_midnight_trip:
			row.customer_name = frappe.db.get_value("Customer", row.customer, "customer_name")

	def before_submit(self):
		pass

	def compute_totals(self):
		
		company_trucks = 0
		transporter_trucks = 0
		self_collect_trucks = 0

		if row.first_trip:
			for row in self.first_trip:
				if row.custom_vehicle_ownership== "Transporter Vehicle":
					transporter_trucks += 1 
				elif row.custom_vehicle_ownership == "Company Vehicle":
					company_trucks += 1
				elif row.custom_vehicle_ownership == "Customer Provided Vehicle":
					self_collect_trucks += 1

		if self.second_trip:
			for row in self.second_trip:
				if row.custom_vehicle_ownership == "Transporter Vehicle":
					transporter_trucks += 1 
				elif row.custom_vehicle_ownership == "Company Vehicle":
					company_trucks += 1
				elif row.custom_vehicle_ownership == "Customer Provided Vehicle":
					self_collect_trucks += 1

		if self.after_midnight_trip:
			for row in self.after_midnight_trip:
				if row.custom_vehicle_ownership == "Transporter Vehicle":
					transporter_trucks += 1
				elif row.custom_vehicle_ownership == "Company Vehicle":
					company_trucks += 1
				elif row.custom_vehicle_ownership == "Customer Provided Vehicle":
					self_collect_trucks += 1

		total_trucks = company_trucks + transporter_trucks + self_collect_trucks

		return company_trucks, transporter_trucks, self_collect_trucks, total_trucks
