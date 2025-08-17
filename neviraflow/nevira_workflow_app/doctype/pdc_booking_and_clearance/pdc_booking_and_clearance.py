# Copyright (c) 2025, Victor Mandela and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from erpnext.accounts.utils import get_account_currency

class PDCBookingandClearance(Document):
    def mark_as_cleared(self):
        if self.clearance_status == "Cleared":
            frappe.throw(_("This document is already marked as Cleared."))

        pe = frappe.new_doc("Payment Entry")
        pe.payment_type = "Receive" if self.party_type == "Customer" else "Pay"
        pe.party_type = self.party_type
        pe.party = self.party_code
        pe.party_name = self.party_name
        pe.posting_date = frappe.utils.nowdate()
        pe.company = self.company or "NEVIRA MINERALS LIMITED"
        pe.paid_amount = self.paid_amount
        pe.received_amount = self.paid_amount
        pe.reference_no = self.cheque_reference_no
        pe.reference_date = self.cheque_reference_date
        pe.mode_of_payment = "Cheque"

        # Resolve valid GL account from Bank Account if needed
        account = None

        # First try to fetch from linked Bank Account doc (account_paid_to / from)
        if self.party_type == "Customer" and self.account_paid_to:
            account = frappe.db.get_value("Bank Account", self.account_paid_to, "account")
        elif self.party_type == "Supplier" and self.account_paid_from:
            account = frappe.db.get_value("Bank Account", self.account_paid_from, "account")

        # Fallback to company bank account if above not set
        if not account and self.company_bank_account:
            account = frappe.db.get_value("Bank Account", self.company_bank_account, "account")

        if not account:
            frappe.throw(_("No valid GL account could be determined for Payment Entry."))

        if self.party_type == "Customer":
            pe.paid_to = account
        else:
            pe.paid_from = account

        # Enable multi-currency if currencies mismatch
        pe_account_currency = get_account_currency(account)
        company_currency = frappe.get_cached_value("Company", pe.company, "default_currency")

        if pe_account_currency != company_currency:
            pe.multi_currency = 1
            pe.target_exchange_rate = 1
            pe.source_exchange_rate = 1

        pe.save()
        pe.submit()

        self.reference_payment_entry = pe.name
        self.set("payment_reference_date", pe.posting_date)
        self.clearance_status = "Cleared"
        self.clearance_date = frappe.utils.nowdate()
        self.save()

        frappe.msgprint(_(f"PDC marked as Cleared. Payment Entry: <a href='/app/payment-entry/{pe.name}'>{pe.name}</a>"))

    def mark_as_bounced(self, charge_amount: float, charge_account: str):
        if self.clearance_status == "Bounced":
            frappe.throw(_("Already marked as Bounced."))

        if not frappe.db.exists("Account", charge_account):
            frappe.throw(_(f"Charge Account '{charge_account}' does not exist. Please provide a valid account name."))

        je = frappe.new_doc("Journal Entry")
        je.voucher_type = "Journal Entry"
        je.posting_date = frappe.utils.nowdate()
        je.company = self.company or "NEVIRA MINERALS LIMITED"
        je.user_remark = f"Bounced Cheque - {self.name}"

        # Updated logic to determine party account
        party_account = frappe.db.get_value(
            "Account",
            {
                "company": je.company,
                "account_type": "Receivable" if self.party_type == "Customer" else "Payable",
                "root_type": "Asset" if self.party_type == "Customer" else "Liability"
            },
            "name"
        )

        if not party_account:
            frappe.throw(_("No party account found for {0} - {1}".format(self.party_type, self.party_code)))

        je.append("accounts", {
            "account": party_account,
            "party_type": self.party_type,
            "party": self.party_code,
            "debit_in_account_currency": charge_amount
        })

        je.append("accounts", {
            "account": charge_account,
            "credit_in_account_currency": charge_amount
        })

        je.save()
        je.submit()

        self.clearance_status = "Bounced"
        self.clearance_date = frappe.utils.nowdate()
        self.save()

        frappe.msgprint(_(f"PDC marked as Bounced. Journal Entry: <a href='/app/journal-entry/{je.name}'>{je.name}</a>"))

    def mark_as_cancelled(self):
        if self.clearance_status == "Cancelled":
            frappe.throw(_("Already cancelled."))

        self.clearance_status = "Cancelled"
        self.clearance_date = frappe.utils.nowdate()
        self.save()

        frappe.msgprint(_(f"PDC marked as Cancelled."))

    def allow_clearance_date_update(self):
        # Allow update only if status is Pending
        return self.clearance_status == "Pending"
