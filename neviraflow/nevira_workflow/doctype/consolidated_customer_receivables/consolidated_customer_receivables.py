# Copyright (c) 2025, Victor Mandela, Billy Adwar & Moses Njue and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate
from erpnext.accounts.report.accounts_receivable.accounts_receivable import execute as ar_execute
from erpnext.accounts.report.accounts_receivable_summary.accounts_receivable_summary import execute as ar_summary_execute
from erpnext.accounts.report.general_ledger.general_ledger import execute as gl_execute


class ConsolidatedCustomerReceivables(Document):
    def validate(self):
        self.validate_from_to_dates()

    def before_save(self):
        email_id, phone_number = frappe.db.get_value('Customer', self.customer,['email_id','mobile_no'])
        self.email_id = email_id
        self.phone_number = phone_number

    def validate_date(self):
        if self.to_date and self.from_date:
            if getdate(self.from_date) > getdate(self.to_date):
                frappe.throw("From Date cannot be after To Date")

    def fetch_all_legder_transaction(self):
        """
        Fetch the general ledger transactions based on the selected from date and to date
        """
        filters = {
            "company": self.company,
            "from_date": self.from_date,
            "to_date": self.to_date,
            "party_type": "Customer",
            "party": [self.customer],
            "group_by": "Group by Voucher (Consolidated)",
            "account_currency": "",
        }
        gl_data = gl_execute(filters)

        ### Really need to check what this part of the code does
        records = gl_data[1] if isinstance(gl_data, tuple) else gl_data

        for row in records:
            if row.get("party") == self.customer:
                cheque_ref = ""
                if row.get("couber_type") == "Payment Entry":
                    cheque_ref = frappe.db.get_value("Payment Entry", row.get("voucher_no"),"reference_no")

                self.append("all_customer_transactions",{
                    "posting_date": row.get("posting_date"),
                    "voucher_type": row.get("voucher_type")
                })

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
	
