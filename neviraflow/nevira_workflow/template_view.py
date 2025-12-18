# Copyright (c) 2025, Victor Mandela, Billy Adwar & Moses Njue and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import today, getdate, flt
from erpnext.accounts.report.accounts_receivable.accounts_receivable import execute as ar_execute
from erpnext.accounts.report.accounts_receivable_summary.accounts_receivable_summary import execute as ar_summary_execute
from erpnext.accounts.report.general_ledger.general_ledger import execute as gl_execute


class ConsolidatedCustomerReceivables(Document):
    def validate(self):
        """Populate all tables when document is validated"""
        self.validate_dates()
        
        if self.customer and self.from_date and self.to_date:
            self.populate_all_customer_transactions()
            self.populate_accounts_receivable_data()
            self.populate_ageing_summary()
    
    def validate_dates(self):
        """Validate that from_date is not after to_date"""
        if self.from_date and self.to_date:
            if getdate(self.from_date) > getdate(self.to_date):
                frappe.throw("From Date cannot be after To Date")
    
    def populate_all_customer_transactions(self):
        """Populate All Customer Transactions table from General Ledger"""
        # Clear existing rows
        self.all_customer_transactions = []
        
        filters = {
            "company": self.company,
            "from_date": self.from_date,
            "to_date": self.to_date,
            "party_type": "Customer",
            "party": [self.customer],
            "group_by": "Group by Voucher (Consolidated)",
            "show_cancelled_entries": False
        }
        
        try:
            gl_data = gl_execute(filters)
            
            if gl_data and len(gl_data) >= 3:
                columns, data = gl_data[0], gl_data[1]
                
                # Map column indices
                col_map = {}
                for idx, col in enumerate(columns):
                    col_map[col.get('fieldname') or col.get('label')] = idx
                
                running_balance = 0
                
                for row in data:
                    posting_date = row.get(col_map.get('posting_date', 0))
                    voucher_type = row.get(col_map.get('voucher_type', 1))
                    voucher_no = row.get(col_map.get('voucher_no', 2))
                    debit = flt(row.get(col_map.get('debit', 0)))
                    credit = flt(row.get(col_map.get('credit', 0)))
                    
                    # Calculate balance
                    running_balance += debit - credit
                    
                    # Get cheque reference for payment entries
                    cheque_ref = ""
                    if voucher_type == "Payment Entry":
                        cheque_ref = frappe.db.get_value("Payment Entry", voucher_no, "reference_no") or ""
                    
                    # Add to child table
                    self.append("all_customer_transactions", {
                        "posting_date": posting_date,
                        "voucher_type": voucher_type,
                        "voucher_no": voucher_no,
                        "cheque_reference_number": cheque_ref,
                        "debit": debit,
                        "credit": credit,
                        "balance": running_balance,
                        "account_currency": self.company_currency or "KES"  # Default currency
                    })
                    
        except Exception as e:
            frappe.log_error(f"Error populating customer transactions: {str(e)}")
            frappe.msgprint(f"Error loading customer transactions: {str(e)}")
    
    def populate_accounts_receivable_data(self):
        """Populate Accounts Receivable Data table"""
        # Clear existing rows
        self.accounts_receivable_data = []
        
        filters = {
            "company": self.company,
            "report_date": self.to_date,
            "ageing_based_on": "Posting Date",
            "party_type": "Customer",
            "party": [self.customer],
            "range1": 30,
            "range2": 60,
            "range3": 90,
            "range4": 120,
            "range5": 0,
            "show_remarks": False,
            "customer": self.customer
        }
        
        try:
            ar_data = ar_execute(filters)
            
            if ar_data and len(ar_data) >= 3:
                columns, data = ar_data[0], ar_data[1]
                
                # Map column indices
                col_map = {}
                for idx, col in enumerate(columns):
                    fieldname = col.get('fieldname', '').lower()
                    if 'posting' in fieldname:
                        col_map['posting_date'] = idx
                    elif 'voucher_type' in fieldname:
                        col_map['voucher_type'] = idx
                    elif 'voucher_no' in fieldname:
                        col_map['voucher_no'] = idx
                    elif 'due' in fieldname:
                        col_map['due_date'] = idx
                    elif 'invoiced' in fieldname:
                        col_map['invoiced_amount'] = idx
                    elif 'paid' in fieldname and 'amount' in fieldname:
                        col_map['paid_amount'] = idx
                    elif 'outstanding' in fieldname:
                        col_map['outstanding_amount'] = idx
                    elif 'range1' in fieldname:
                        col_map['range1'] = idx
                    elif 'range2' in fieldname:
                        col_map['range2'] = idx
                    elif 'range3' in fieldname:
                        col_map['range3'] = idx
                    elif 'range4' in fieldname:
                        col_map['range4'] = idx
                    elif 'range5' in fieldname:
                        col_map['range5'] = idx
                
                for row in data:
                    # Skip total rows
                    if isinstance(row, dict) and row.get('voucher_type') == 'Total':
                        continue
                    
                    self.append("accounts_receivable_data", {
                        "posting_date": row.get(col_map.get('posting_date')),
                        "voucher_type": row.get(col_map.get('voucher_type')),
                        "voucher_no": row.get(col_map.get('voucher_no')),
                        "due_date": row.get(col_map.get('due_date')),
                        "invoiced_amount": flt(row.get(col_map.get('invoiced_amount', 0))),
                        "credit_note": 0,  # Will be calculated separately
                        "paid_amount": flt(row.get(col_map.get('paid_amount', 0))),
                        "range1": flt(row.get(col_map.get('range1', 0))),
                        "range2": flt(row.get(col_map.get('range2', 0))),
                        "range3": flt(row.get(col_map.get('range3', 0))),
                        "range4": flt(row.get(col_map.get('range4', 0))),
                        "range5": flt(row.get(col_map.get('range5', 0))),
                        "outstanding_amount": flt(row.get(col_map.get('outstanding_amount', 0)))
                    })
                    
        except Exception as e:
            frappe.log_error(f"Error populating accounts receivable data: {str(e)}")
            frappe.msgprint(f"Error loading accounts receivable data: {str(e)}")
    
    def populate_ageing_summary(self):
        """Populate Ageing Summary table"""
        # Clear existing rows
        self.ageing_summary = []
        
        filters = {
            "company": self.company,
            "report_date": self.to_date,
            "ageing_based_on": "Posting Date",
            "party_type": "Customer",
            "range1": 30,
            "range2": 60,
            "range3": 90,
            "range4": 120,
            "range5": 0,
            "customer": self.customer
        }
        
        try:
            ar_summary_data = ar_summary_execute(filters)
            
            if ar_summary_data and len(ar_summary_data) >= 3:
                columns, data = ar_summary_data[0], ar_summary_data[1]
                
                # Map column indices
                col_map = {}
                for idx, col in enumerate(columns):
                    fieldname = col.get('fieldname', '').lower()
                    label = col.get('label', '').lower()
                    
                    if 'customer' in fieldname or 'customer' in label:
                        col_map['customer'] = idx
                    elif 'invoiced' in fieldname or 'invoiced' in label:
                        col_map['invoiced_amount'] = idx
                    elif 'paid' in fieldname and 'amount' in (fieldname or label):
                        col_map['paid_amount'] = idx
                    elif 'outstanding' in fieldname or 'outstanding' in label:
                        col_map['outstanding_amount'] = idx
                    elif 'range1' in fieldname:
                        col_map['range1'] = idx
                    elif 'range2' in fieldname:
                        col_map['range2'] = idx
                    elif 'range3' in fieldname:
                        col_map['range3'] = idx
                    elif 'range4' in fieldname:
                        col_map['range4'] = idx
                    elif 'range5' in fieldname:
                        col_map['range5'] = idx
                    elif 'total' in fieldname or 'total' in label:
                        col_map['total'] = idx
                
                for row in data:
                    # Skip if it's a total row or doesn't match our customer
                    if (isinstance(row, dict) and 
                        (row.get('customer') != self.customer and not any(field in str(row).lower() for field in ['total', 'grand']))):
                        continue
                    
                    # Calculate credit notes separately
                    credit_notes = self.get_credit_notes_amount()
                    
                    self.append("ageing_summary", {
                        "customer_name": row.get(col_map.get('customer')) or self.customer,
                        "invoiced_amount": flt(row.get(col_map.get('invoiced_amount', 0))),
                        "paid_amount": flt(row.get(col_map.get('paid_amount', 0))),
                        "credit_note": credit_notes,
                        "outstanding_amount": flt(row.get(col_map.get('outstanding_amount', 0))),
                        "range1": flt(row.get(col_map.get('range1', 0))),
                        "range2": flt(row.get(col_map.get('range2', 0))),
                        "range3": flt(row.get(col_map.get('range3', 0))),
                        "range4": flt(row.get(col_map.get('range4', 0))),
                        "range5": flt(row.get(col_map.get('range5', 0))),
                        "total_amount_due": flt(row.get(col_map.get('total', 0)))
                    })
                    
        except Exception as e:
            frappe.log_error(f"Error populating ageing summary: {str(e)}")
            frappe.msgprint(f"Error loading ageing summary: {str(e)}")
    
    def get_credit_notes_amount(self):
        """Calculate total credit notes for the customer within date range"""
        try:
            credit_notes = frappe.db.sql("""
                SELECT SUM(credit_note.grand_total) 
                FROM `tabSales Invoice` as credit_note
                WHERE credit_note.customer = %s
                AND credit_note.posting_date BETWEEN %s AND %s
                AND credit_note.docstatus = 1
                AND credit_note.is_return = 1
            """, (self.customer, self.from_date, self.to_date))
            
            return flt(credit_notes[0][0]) if credit_notes else 0
        except Exception as e:
            frappe.log_error(f"Error calculating credit notes: {str(e)}")
            return 0
    
    def on_update(self):
        """Refresh data when document is saved"""
        if self.customer and self.from_date and self.to_date:
            frappe.msgprint("Customer Receivables Data Updated Successfully")
    
    def get_accounts_receivable_data(self):
        """Legacy method - kept for compatibility"""
        return self.populate_accounts_receivable_data()
    
    def get_accounts_receivable_summary(self):
        """Legacy method - kept for compatibility"""
        return self.populate_ageing_summary()
    
    def get_all_ledger_transactions(self):
        """Legacy method - kept for compatibility"""
        return self.populate_all_customer_transactions()





###############################################################################


###############################################################################

# Copyright (c) 2025, Victor Mandela, Billy Adwar & Moses Njue and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, today, getdate

# Import the specific execute functions for the reports
from erpnext.accounts.report.accounts_receivable.accounts_receivable import execute as ar_execute
from erpnext.accounts.report.accounts_receivable_summary.accounts_receivable_summary import execute as ar_summary_execute
from erpnext.accounts.report.general_ledger.general_ledger import execute as gl_execute

class ConsolidatedCustomerReceivables(Document):
    
    def validate(self):
        """
        We use validate instead of before_save to ensure data is fetched 
        and validated before the commit to the database happens.
        """
        self.validate_mandatory_fields()
        
        # Clear existing rows to prevent duplication on re-save
        self.set("all_customer_transactions", [])
        self.set("accounts_receivable_data", [])
        self.set("ageing_summary", [])
        
        # Populate the tables
        self.fetch_all_ledger_transactions()
        self.fetch_accounts_receivable_data()
        self.fetch_accounts_receivable_summary()

    def validate_mandatory_fields(self):
        if not self.customer:
            frappe.throw(_("Please select a Customer."))
        if not self.from_date or not self.to_date:
            frappe.throw(_("Please select both From Date and To Date."))

    def fetch_all_ledger_transactions(self):
        """
        Fetches data from General Ledger based on Date Range.
        """
        # Prepare filters for GL Report
        filters = {
            "company": self.company,
            "from_date": self.from_date,
            "to_date": self.to_date,
            "party_type": "Customer",
            "party": [self.customer],
            "group_by": "Group by Voucher (Consolidated)", # Optional: Cleaner view
            "account_currency": frappe.db.get_value("Customer", self.customer, "default_currency") or self.company_currency
        }

        # GL Execute returns a list of dictionaries
        gl_data = gl_execute(filters)
        
        # GL execute might return (columns, data) or just data depending on version
        # We ensure we are working with the list of data
        records = gl_data[1] if isinstance(gl_data, tuple) else gl_data

        for row in records:
            # We filter for the specific customer again just to be safe, 
            # though the report filter usually handles it.
            if row.get("party") == self.customer:
                
                # Fetch Cheque Reference Number if it's a Payment Entry
                cheque_ref = ""
                if row.get("voucher_type") == "Payment Entry":
                    cheque_ref = frappe.db.get_value("Payment Entry", row.get("voucher_no"), "reference_no")
                
                self.append("all_customer_transactions", {
                    "posting_date": row.get("posting_date"),
                    "voucher_type": row.get("voucher_type"),
                    "voucher_no": row.get("voucher_no"),
                    "cheque_reference_number": cheque_ref, # Custom fetch logic
                    "debit": flt(row.get("debit")),
                    "credit": flt(row.get("credit")),
                    "balance": flt(row.get("balance")),
                    "account_currency": row.get("account_currency")
                })

    def fetch_accounts_receivable_data(self):
        """
        Fetches data from Accounts Receivable Report.
        """
        # Common settings for AR reports
        filters = {
            "company": self.company,
            "report_date": self.to_date, # AR is always 'as of' this date
            "party_type": "Customer",
            "party": [self.customer],
            "ageing_based_on": "Posting Date",
            "range1": 30,
            "range2": 60,
            "range3": 90,
            "range4": 120,
            "range5": 150, # Optional buffer
            "show_remarks": False
        }

        # AR Execute returns (columns, data)
        columns, data = ar_execute(filters)

        for row in data:
            # Note: The keys in 'row' correspond to fieldnames in the report.
            # Usually: 'posting_date', 'voucher_type', 'voucher_no', etc.
            
            self.append("accounts_receivable_data", {
                "posting_date": row.get("posting_date"),
                "voucher_type": row.get("voucher_type"),
                "voucher_no": row.get("voucher_no"),
                "due_date": row.get("due_date"),
                "invoiced_amount": flt(row.get("invoiced_amount") or row.get("invoice_amount")), # Key varies by version
                "credit_note": flt(row.get("credit_note_amount")),
                "paid_amount": flt(row.get("paid_amount")),
                "outstanding_amount": flt(row.get("outstanding_amount")),
                # The ranges are usually returned as keys 'range1', 'range2' etc. 
                # If using standard report, they might be strictly mapped to column labels.
                # We assume standard keys here:
                "range1": flt(row.get("range1")),
                "range2": flt(row.get("range2")),
                "range3": flt(row.get("range3")),
                "range4": flt(row.get("range4")),
                "range5": flt(row.get("range5"))
            })

    def fetch_accounts_receivable_summary(self):
        """
        Fetches data from Accounts Receivable Summary.
        """
        filters = {
            "company": self.company,
            "report_date": self.to_date,
            "party_type": "Customer",
            "party": [self.customer],
            "ageing_based_on": "Posting Date",
            "range1": 30,
            "range2": 60,
            "range3": 90,
            "range4": 120
        }

        # Execute Summary Report
        columns, data = ar_summary_execute(filters)

        for row in data:
            # Since we filter by specific customer, this loop usually runs once
            # or multiple times if the customer has multiple currencies.
            
            self.append("ageing_summary", {
                "customer_name": row.get("party_name") or self.customer,
                "invoiced_amount": flt(row.get("billed_amt")), # 'billed_amt' is common key in summary
                "paid_amount": flt(row.get("paid_amt")),
                "credit_note": flt(row.get("credit_note_amt")),
                "outstanding_amount": flt(row.get("outstanding_amt")),
                "range1": flt(row.get("range1")),
                "range2": flt(row.get("range2")),
                "range3": flt(row.get("range3")),
                "range4": flt(row.get("range4")),
                "range5": flt(row.get("range5")),
                "total_amount_due": flt(row.get("outstanding_amt"))
            })

    @property
    def company_currency(self):
        """Helper to get company currency"""
        return frappe.get_cached_value('Company', self.company,  "default_currency")