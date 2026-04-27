# Copyright (c) 2025, Victor Mandela, Billy Adwar & Moses Njue and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from erpnext.accounts.report.accounts_receivable.accounts_receivable import execute as ar_execute
from erpnext.accounts.report.accounts_receivable_summary.accounts_receivable_summary import execute as ar_summary_execute
from erpnext.accounts.report.general_ledger.general_ledger import execute as gl_execute
from frappe.utils import add_days, today, getdate, flt
from erpnext.accounts.party import get_party_account, get_party_details
from erpnext.accounts.party import get_due_date, get_party_account, get_party_details


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
        self.set("pending_pd_cheques",[])


        #### Populate the tables here
        self.fetch_general_ledger_transactions()
        self.fetch_accounts_receivable_data()
        self.fetch_accounts_receivable_summary()
        self.fetch_customer_pd_cheques()
        

    def before_save(self):
        customer_name, email_id, phone_number = frappe.db.get_value('Customer', self.customer,['customer_name','email_id','mobile_no'])
        self.payment_terms = frappe.db.get_value("Customer",self.customer,'payment_terms')
        customer_credit_limit = frappe.db.get_value("Customer Credit Limit",{"parent": self.customer, "parenttype": "Customer"}, 'credit_limit')
        self.credit_limit = customer_credit_limit or 0.00
        self.email_id = email_id
        self.phone_number = phone_number
        self.customer_name = customer_name

        sales_person_query = frappe.db.get_value('Sales Team', {"parent":self.customer, "parenttype":"Customer"}, 'sales_person')
        self.sales_person = sales_person_query or ""
        self.sales_person_email = frappe.db.get_value('Customer', self.customer, 'account_manager')
        self.total_outstanding_amount = self.get_customer_balance()

        ## Get and set the party's account currency
        party_account = get_party_account("Customer",self.customer, "NEVIRA MINERALS LTD")
        currency = frappe.db.get_value("Account", party_account, "account_currency")
        self.account_currency = currency

    def validate_dates(self):
        if self.to_date and self.from_date:
            if getdate(self.from_date) > getdate(self.to_date):
                frappe.throw("From Date cannot be after To Date")

    def before_submit(self):
        pdc_total = 0

        for pdc_item in self.pending_pd_cheques:
            pdc_total += pdc_item.amount or 0
        
        self.total_pdc_amount = pdc_total


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
            "show_opening_entries": 1,
            "add_values_in_transaction_currency":1
        }

       
       
        filters_  = frappe._dict(filters)

        ## Clear the child table first before populating it with data
        self.all_customer_transactions = []

        ## From the execution of the report we only want to get the data and not the columns
        try:
            gl_data = gl_execute(filters_)
            if gl_data and len(gl_data) > 1:

                all_transactions_list = gl_data[1]

                for row in all_transactions_list:
                    cheque_ref = ""
                    export_series = ""

                    if row.get("voucher_type") == "Payment Entry":
                        pe_number = row.get("voucher_no")
                        cheque_ref += frappe.db.get_value("Payment Entry",pe_number, "reference_no")
                        currency = frappe.db.get_value("Account",row.get("account"),"account_currency")

                    if row.get("voucher_type") == "Sales Invoice":
                        invoice_id = row.get("voucher_no")
                        series = frappe.db.get_value('Sales Invoice', invoice_id,"export_series") or ""
                        export_series += series

                    self.append("all_transactions",{
                        "posting_date":row.get("posting_date"),
                        "account": row.get("account"),
                        "voucher_type":row.get("voucher_type"),
                        "voucher_no":row.get("voucher_no"),
                        "export_series": export_series,
                        "cheque_reference_no": cheque_ref,
                        "debit": flt(row.get("debit")),
                        "credit": flt(row.get("credit")),
                        "balance":flt(row.get("balance")),
                        "account_currency":row.get("transaction_currency")
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
            "calculate_ageing_with": "Today Date",
            "in_party_currency": 1
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

                        export_series = ""
                        if row.get("voucher_type") == "Sales Invoice":

                            invoice_id = row.get("voucher_no")
                            series = frappe.db.get_value('Sales Invoice', invoice_id, "export_series") or ""
                            export_series += series

                        self.append("unpaid_invoices",{
                            "posting_date": row.get("posting_date"),
                            "voucher_type": row.get("voucher_type"),
                            "voucher_no": row.get("voucher_no"),
                            "export_series": export_series,
                            "due_date": row.get("due_date") if row.get("due_date") else "",
                            "invoiced_amount": flt(row.get("invoice_grand_total")),
                            "credit_note": flt(row.get("credit_note")),
                            "paid_amount": flt(row.get("paid")),
                            "range1": flt(row.get("range1")),
                            "range2": flt(row.get("range2")),
                            "range3": flt(row.get("range3")),
                            "range4": flt(row.get("range4")),
                            "range5": flt(row.get("range5")),
                            "outstanding_amount": flt(row.get("outstanding")),
                            "currency": row.get("currency")
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
                            "invoiced_amount": flt(row.get("invoiced")),
                            "paid_amount": flt(row.get("paid")),
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

            
    ## Get the customer's balance from the ledger 
    def get_customer_balance(self):
        customer_id = self.customer
        balance_query = frappe.db.sql(""" SELECT (SUM(debit) - SUM(credit)) AS balance 
                FROM `tabGL Entry` WHERE party = %s""",
                (customer_id), as_dict=True) 
        if balance_query:
            balance = balance_query[0]["balance"]
            return balance
        else:
            return 0.00

    def fetch_customer_pd_cheques(self):
        customer_id = self.customer
        filters = {
            "pdc_type": "Customer PDC",
            "clearance_status": "Pending",
            "party_code": customer_id,
            "docstatus": 1
        }

        filters_  = frappe._dict(filters)

        self.pending_pd_cheques = []

        pd_cheques = frappe.db.get_list("PDC Booking and Clearance",
                                filters = filters_, fields =  ["name","pdc_type","cheque_reference_no","clearance_date","clearance_status","paid_amount"])
        
        if not pd_cheques:
            return
        try: 
            if pd_cheques:
                for pdc_data in pd_cheques:
                    self.append("pending_pd_cheques",{
                        "pd_cheque_id": pdc_data.get("name"),
                        "clearance_date": pdc_data.get("clearance_date"),
                        "cheque_number": pdc_data.get("cheque_reference_no"),
                        "amount": pdc_data.get("paid_amount")
                    })
        except:
            frappe.log_error("Failed to fetch and load PDC data")

        
def get_balance(customer):
    balance_query = frappe.db.sql(""" SELECT (SUM(debit) - SUM(credit)) AS balance 
                FROM `tabGL Entry` WHERE party = %s""",
                (customer), as_dict=True) 
    if balance_query:
        balance = balance_query[0]["balance"]
        return balance
    else:
        return 0.00
    