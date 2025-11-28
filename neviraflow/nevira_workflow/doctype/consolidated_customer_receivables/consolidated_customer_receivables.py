# Copyright (c) 2025, Victor Mandela, Billy Adwar & Moses Njue and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import today, add_days
from erpnext.accounts.report.accounts_receivable.accounts_receivable import execute as ar_execute
from erpnext.accounts.report.accounts_receivable_summary.accounts_receivable_summary import execute as ar_summary_execute
from erpnext.accounts.report.general_ledger.general_ledger import execute as gl_execute


class ConsolidatedCustomerReceivables(Document):
## What do I do if I want to define variables such as customer_name from self as global ?
    def before_save(self):
        pass

    def validate_date(self):
        pass
    def get_accounts_receivable_data(self):
        customer = self.customer_name
        to_date = self.to_date
        company = self.company
        get_unpaid_only = self.get_unpaid_only

        if get_unpaid_only:
            filters = {
                "company": company,
                "party_type": "Customer",
                "party": [customer],
                "range1": 30,
                "range2": 60,
                "range3": 90,
                "range4": 120,
                "show_remarks": False
            }
            ar_report = ar_execute(filters)
            return ar_report

    def get_accounts_receivable_summary(self):
        pass
            

    def get_all_ledger_transctions(self):
        pass
	
