# Copyright (c) 2025, Victor Mandela, Billy Adwar & Moses Njue and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from erpnext.accounts.report.accounts_receivable.accounts_receivable import execute as ar_execute
from erpnext.accounts.report.accounts_receivable_summary.accounts_receivable_summary import execute as ar_summary_execute
from erpnext.accounts.report.general_ledger.general_ledger import execute as gl_execute
from frappe.utils import add_days, today, getdate, flt


class ConsolidatedCustomerReceivables(Document):
    def validate(self):
        """
        Ideally these methods should go into the before_save method, but I want them here because I want to do the validation
        and fetching before data is saved
        """
        self.validate_dates()

        #### Clear the tables first
        self.set("all_transactions",[])
        self.set("unpaid_invoices",[])
        self.set("ageing_summary",[])


        #### Populate the tables here
        self.fetch_general_ledger_transactions()
        self.fetch_accounts_receivable_data()
        self.fetch_accounts_receivable_summary()

    def before_save(self):
        email_id, phone_number = frappe.db.get_value('Customer', self.customer,['email_id','mobile_no'])
        self.email_id = email_id
        self.phone_number = phone_number

    def validate_dates(self):
        if self.to_date and self.from_date:
            if getdate(self.from_date) > getdate(self.to_date):
                frappe.throw("From Date cannot be after To Date")

    def fetch_general_ledger_transactions(self):
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
            "show_opening_entries": 1
        }
        filters_  = frappe._dict(filters)

        ## Clear the child table first before populating it with data
        self.all_customer_transactions = []

        ## From the execution of the report we only want to get the data and not the columns
        try:
            gl_data = gl_execute(filters_)
            if gl_data and len(gl_data) > 1:

                all_transactions_list = gl_data[1]

                all_transactions_data = all_transactions_list[:-2]

                for row in all_transactions_data:
                    cheque_ref = ""
                    if row.get("voucher_type") == "Payment Entry":
                        cheque_ref = frappe.db.get_value("Payment Entry",row.get("voucher_no"), "reference_no")
                        currency = frappe.db.get_value("Account",row.get("account"),"account_currency")

                    self.append("all_transactions",{
                        "posting_date":row.get("posting_date"),
                        "voucher_type":row.get("voucher_type"),
                        "voucher_no":row.get("voucher_no"),
                        "cheque_reference_no": cheque_ref,
                        "debit": flt(row.get("debit")),
                        "credit": flt(row.get("credit")),
                        "balance":flt(row.get("balance")),
                        "account_currency":currency
                    })
        except Exception as e:
            frappe.log_error(f"Error encountered in fetching and populating general ledger data: {str(e)}")
            frappe.msgprint(f"Error loading GL Data {str(e)}")



    def fetch_accounts_receivable_data(self):
        """
        Fetches data frm the accounts receivable report
        """
        filters = {
            "company": self.company,
            "report_date": getdate(),
            "party_type": "Customer",
            "party": [self.customer],
            "ageing_based_on": "Due Date",
            "range": "30, 60, 90, 120",
            "calculate_ageing_with": "Today Date"
        }
        filters_  = frappe._dict(filters)
        
        ### Before populating the child table with data, first clear the child table
        self.unpaid_invoices = []
        
        try:
            receivables_data = ar_execute(filters_)
            if receivables_data:
                receivables_list = receivables_data[1]
                if len(receivables_list) > 0:
                    for row in receivables_list:
                        self.append("unpaid_invoices",{
                            "posting_date": row.get("posting_date"),
                            "voucher_type": row.get("voucher_type"),
                            "voucher_no": row.get("voucher_no"),
                            "due_date": row.get("due_date") if row.get("due_date") else "",
                            "invoiced_amount": flt(row.get("invoiced_grand_total")),
                            "credit_note": flt(row.get("credit_note")),
                            "paid_amount": flt(row.get("paid")),
                            "range1": flt(row.get("range1")),
                            "range2": flt(row.get("range2")),
                            "range3": flt(row.get("range3")),
                            "range4": flt(row.get("range4")),
                            "range5": flt(row.get("range5")),
                            "outstanding_amount": flt(row.get("outstanding"))
                        })
        except Exception as e:
            frappe.log_error(f"Error in fetching the accounts receivables data {str(e)}")
            frappe.msgprint(f"Error encountered in fetching accounts receivable data: {str(e)}")


    def fetch_accounts_receivable_summary(self):
        """
        Get the summarised data from the accounts receivable summary and populate the child table
        """
        filters = {
            "company": self.company,
            "report_date": getdate(),
            "party_type": "Customer",
            "party":[self.customer],
            "ageing_based_on": "Due Date",
            "range": "30, 60, 90, 120",
            "calculate_ageing_with": "Today Date"
        }
        filters_ = frappe._dict(filters)

        ### Before populating the child table with data, first clear the child table
        self.ageing_summary = []

        try:
            ar_summary_data = ar_summary_execute(filters_)

            if ar_summary_data:
                ar_summary_list = ar_summary_data[1]

                if len(ar_summary_list) > 0:
                    for row in ar_summary_list:
                        self.append("ageing_summary",{
                            "customer_name": row.get("party_name"),
                            "invoiced_amount": flt(row.get("invoiced_amount")),
                            "paid_amount": flt(row.get("paid_amount")),
                            "credit_note": flt(row.get("credit_note")),
                            "outstanding_amount": flt(row.get("outstanding")),
                            "range1": flt(row.get("range1")),
                            "range2": flt(row.get("range2")),
                            "range3": flt(row.get("range3")),
                            "range4": flt(row.get("range4")),
                            "range5": flt(row.get("range5")),
                            "total_amount_due": flt(row.get("total_due"))
                        })

        except Exception as e:
            frappe.log_error(f" Failed to fetch the accounts receivable summary {str(e)}")
            frappe.msgprint(f" Failed to fetch and populate the acconts receivable summary {str(e)}")

            


