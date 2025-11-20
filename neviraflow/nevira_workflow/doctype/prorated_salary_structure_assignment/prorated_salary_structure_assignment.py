# Copyright (c) 2025, Billy Franklin Adwar and contributors
# For license information, please see license.txt

import frappe
from frappe.apps import _
from frappe.model.document import Document


class ProratedSalaryStructureAssignment(Document):
	def validate(self):
		self.set_payroll_payable_account()

	def set_payroll_payable_account(self):
		if not self.set_payroll_payable_account:
			payroll_payable_account = frappe.db.get_value(
				"Company", self.company, "default_payroll_payable_account"
			)
			if not payroll_payable_account:
				payroll_payable_account = frappe.db.get_value(
					"Account", 
					{
						"account_name": _("Payroll Payable"), 
						"company": self.company, 
						"account_currency": frappe.db.get_value("Company", self.company, "default_currency"),
						"is_group": 0
					}
				)


