# Copyright (c) 2026, Victor Mandela, Billy Adwar & Moses Njue and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate, today
from frappe.model.document import Document


class CasualsPayrollEntry(Document):
	def validate(self):
		self.validate_dates()

	def validate_dates(self):
		if not self.from_date or not self.to_date:
			frappe.throw("Please select from date and to date")

		if getdate(self.from_date) > getdate(self.to_date):
			frappe.throw("From date cannot be after to date")

	def get_casuals_working_days_and_rate(self):
		query = """ 
				WITH attendance_data AS (
					SELECT 
						att.name, att.casual_staff, cas.full_name,cas.daily_rate, att.attendance_date, att.attendance_status, 
						CASE
							WHEN att.attendance_status = 'Present' THEN 1 
							WHEN att.attendance_status ='Half Day' THEN 0.5
						END AS attendance_flag,att.department  
					FROM `tabCasual Staff Attendance`  AS att
					INNER JOIN `tabCasual Staff` AS cas ON att.casual_staff = cas.name 
					WHERE att.docstatus = 1
				)
				SELECT 
					casual_staff, full_name, daily_rate, SUM(attendance_flag) AS days,
					SUM(attendance_flag) * daily_rate AS gross_pay
				FROM attendance_data
				GROUP BY casual_staff """
		result_set = frappe.db.sql(query, as_dict=True)
		try:
			return result_set
		except Exception as e:
			frappe.log_error("Could not find any casual employees for the selected period", (e))



	def populate_payroll_entry_table(self):
		""" This function will extract the casual employees and set them in the casuals table"""

		## Clear the table first
		self.casual_staff_details = []

		casuals_data = self.get_casuals_working_days_and_rate()

		for data in casuals_data:
			self.append("casual_staff_details",{
				"casual_staff":data.casual_staff,
				"full_name": data.full_name,
				"daily_rate": data.daily_rate,
				"days_worked": data.days_worked,
				"gross_pay": data.gross_pay
			})

		frappe.msgprint(f"Added the casuals pay data for {len(data)} casuals staff")
		return True


	def create_salary_slips(self):
		salary_slips_created = []
		for data in self.casual_staff_details:
			existing_casuals_slip = frappe.db.exists("Casuals Salary Slip",{
				"casual_staff": data.casual_staff,
				"payroll_date": self.from_date,
				"docstatus": 1
			})

			if existing_casuals_slip:
				frappe.msgprint(f"Salary slip already exists for employee", raise_exception = True)
				continue

			salary_slip_doc = frappe.new_doc("Casuals Salary Slip")

			#frappe.db.get_value("Casuals Additional Salary", data.casual_staff, [])

			salary_slip_doc.update({
				"casual_staff": data.casual_staff,
				"full_name" : data.full_name,
				"posting_date":self.posting_date,
				"payroll_date": self.from_date
			})
