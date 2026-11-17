# Copyright (c) 2026, Victor Mandela, Billy Adwar & Moses Njue and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import get_time, getdate, today, time_diff_in_hours
from frappe.model.document import Document

class CasualStaffAttendance(Document):
	def validate(self):
		self.validate_attendance_date()
		self.validate_duplicate_attendance()
		self.validate_joining_date()

	def before_save(self):
		self.fetch_casual_staff_details()
		self.calculate_hours_worked()

	def validate_attendance_date(self):
		""" Prevent having an attendance in the future"""

		if getdate(self.attendance_date)  > getdate(today()):
			frappe.throw("Attendance Date cannot be greater than today")

	def validate_duplicate_attendance(self):
		""" Prevent having more than one attendance record on the same day """
		existing_attendance = frappe.db.exists("Casual Staff Attendance",{
			"casual_staff" : self.casual_staff,
			"attendance_date": self.attendance_date
		})
		if existing_attendance:
			frappe.throw(f"Attendance for casual <b>{self.casual_staff}</b> already exists for the current date")


	def validate_joining_date(self):
		""" We cannot have the attendance date earlier than the joining date"""
		joining_date = frappe.db.get_value("Casual Staff", self.casual_staff, "date_of_joining")
		if getdate(self.attendance) < getdate(joining_date):
			frappe.throw(f"Attendance date cannot be earlier than the staff joing date")
	
	def fetch_casual_staff_details(self):
		"""Fetch some details i.e department and section, from the casual doctype"""

		if not self.casual_staff: 
			return
		staff_details = frappe.db.get_value("Casual Staff", self.casual_staff,["department","section"],
		                                    as_dict=True)
		if staff_details:
			self.department = staff_details["department"]
			self.section = staff_details["section"]

	def calculate_hours_worked(self):
		"""Compute the number of hours the casual employee has worked"""
		if not self.time_in or not self.time_out:
			self.hours_worked = 0
			return


		self.hours_worked = round(time_diff_in_hours(self.time_out, self.time_in),2)


