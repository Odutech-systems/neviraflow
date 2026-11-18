# Copyright (c) 2026, Victor Mandela, Billy Adwar & Moses Njue and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate, today
from frappe.model.document import Document


class CasualsPayrollEntry(Document):
	def get_casuals_working_days_and_rate(self):
		query = """ 
				WITH attendance_data AS (
					SELECT 
						att.name, 
						att.casual_staff, 
						cas.full_name,
						cas.daily_rate,
						att.attendance_date, 
						att.attendance_status, 
						CASE
							WHEN att.attendance_status = 'Present' THEN 1 
							WHEN att.attendance_status ='Half Day' THEN 0.5
						END AS attendance_flag,
						att.department  
					FROM `tabCasual Staff Attendance`  AS att
					INNER JOIN `tabCasual Staff` AS cas ON att.casual_staff = cas.name 
					WHERE att.docstatus = 1
				)
				SELECT 
					casual_staff, 
					full_name, 
					daily_rate,
					SUM(attendance_flag) AS days,
					SUM(attendance_flag) * daily_rate AS gross_pay
				FROM attendance_data
				GROUP BY casual_staff
				"""
		result_set = frappe.db.sql(query, as_dict=True)
		if result_set:
			return result_set
		else:
			return


	def populate_payroll_entry_table(self):
		pass




def create_salary_slips():
	pass