# Copyright (c) 2025, Victor Mandela and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from erpnext.accounts.utils import get_account_currency
from erpnext.accounts.party import get_party_account

class PDCBookingandClearance(Document):

    # ✅ Helper: Check if the PDC is finalized (no further changes allowed)
    def is_finalized(self):
        return self.clearance_status in ["Cleared", "Bounced", "Cancelled"]

    # ✅ NEW: Allow clearance date update only if not finalized
    def allow_clearance_date_update(self):
        return not self.is_finalized()

    def mark_as_cleared(self):
        if self.is_finalized():
            frappe.throw(_("This cheque has already been settled and cannot be cleared."))

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

        account = None
        if self.party_type == "Customer" and self.account_paid_to:
            account = frappe.db.get_value("Bank Account", self.account_paid_to, "account")
        elif self.party_type == "Supplier" and self.account_paid_from:
            account = frappe.db.get_value("Bank Account", self.account_paid_from, "account")
        if not account and self.company_bank_account:
            account = frappe.db.get_value("Bank Account", self.company_bank_account, "account")

        if not account:
            frappe.throw(_("No valid GL account could be determined for Payment Entry."))

        if self.party_type == "Customer":
            pe.paid_to = account
        else:
            pe.paid_from = account

        pe_account_currency = get_account_currency(account)
        company_currency = frappe.get_cached_value("Company", pe.company, "default_currency")

        if pe_account_currency != company_currency:
            pe.multi_currency = 1
            pe.target_exchange_rate = 1
            pe.source_exchange_rate = 1

        pe.save()
        pe.submit()
        frappe.db.commit()

        self.reference_payment_entry = pe.name
        self.set("payment_reference_date", pe.posting_date)
        self.clearance_status = "Cleared"
        self.clearance_date = frappe.utils.nowdate()
        self.save()

        frappe.msgprint(_(f"PDC marked as Cleared. Payment Entry: <a href='/app/payment-entry/{pe.name}'>{pe.name}</a>"))

    def mark_as_bounced(self, charge_amount: float, charge_account: str):
        if self.is_finalized():
            frappe.throw(_("This cheque has already been settled and cannot be marked as Bounced."))

        if not frappe.db.exists("Account", charge_account):
            frappe.throw(_(f"Charge Account '{charge_account}' does not exist."))

        je = frappe.new_doc("Journal Entry")
        je.voucher_type = "Journal Entry"
        je.posting_date = frappe.utils.nowdate()
        je.company = self.company or "NEVIRA MINERALS LIMITED"
        je.user_remark = f"Bounced Cheque - {self.name}"

        # ✅ Get correct party account
        party_account = get_party_account(self.party_type, self.party_code, self.company)

        # ➕ Debit the customer
        je.append("accounts", {
            "account": party_account,
            "party_type": self.party_type,
            "party": self.party_code,
            "debit_in_account_currency": charge_amount
        })

        # ➖ Credit the bounce fee account
        je.append("accounts", {
            "account": charge_account,
            "credit_in_account_currency": charge_amount
        })

        # ✅ Handle currency mismatch
        party_currency = get_account_currency(party_account)
        charge_currency = get_account_currency(charge_account)
        company_currency = frappe.get_cached_value("Company", je.company, "default_currency")

        if party_currency != charge_currency or party_currency != company_currency:
            je.multi_currency = 1
            for line in je.accounts:
                line.exchange_rate = 1

        je.save()
        je.submit()

        self.clearance_status = "Bounced"
        self.clearance_date = frappe.utils.nowdate()
        self.save()

        frappe.msgprint(_(f"PDC marked as Bounced. Journal Entry: <a href='/app/journal-entry/{je.name}'>{je.name}</a>"))

    def mark_as_cancelled(self, comment=None):
        if self.is_finalized():
            frappe.throw(_("This cheque has already been settled and cannot be cancelled."))

        self.clearance_status = "Cancelled"
        self.clearance_date = frappe.utils.nowdate()

        if comment:
            self.cancel_comment = comment  # ✅ Make sure this field exists on the DocType

        self.save()
        frappe.msgprint(_("PDC marked as Cancelled."))
