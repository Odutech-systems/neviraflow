# Copyright (c) 2026, Victor Mandela, Billy Adwar & Moses Njue and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import get_datetime, getdate, date_diff, today, get_time, time_diff_in_hours
from datetime import datetime
from frappe.model.document import Document


class CasualStaff(Document):
	def validate(self):
		self.set_casual_staff_name()

	def validate(self):
		self.validate_date()


	def validate_date(self):
		if self.date_of_birth and getdate(self.date_of_birth) > getdate(today()):
			frappe.throw(_("Date of birth cannot be greater than current date"))

	def set_casual_staff_name(self):
		self.full_name = " ".join(
			filter(lambda x: x, [self.first_name, self.middle_name, self.last_name])
		)