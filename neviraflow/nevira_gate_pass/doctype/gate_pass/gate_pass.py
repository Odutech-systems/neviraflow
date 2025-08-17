# Copyright (c) 2025, Victor Mandela and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from datetime import datetime

class GatePass(Document):
    def autoname(self):
        if self.gate_pass_type == "Outgoing":
            prefix = "GPO"
        elif self.gate_pass_type == "Incoming":
            prefix = "GPIN"
        else:
            frappe.throw("Invalid Gate Pass Type")

        now = datetime.now()
        mm = now.strftime("%m")
        yy = now.strftime("%y")
        series_key = f"{prefix}{mm}{yy}"
        self.gate_pass_id = frappe.model.naming.make_autoname(f"{series_key}.###")
        self.name = self.gate_pass_id

    def before_submit(self):
        now = datetime.now()
        self.submitted_date = now.date()
        self.submitted_time = now.time().strftime("%H:%M:%S")
        self.gate_pass_status = "Completed"

@frappe.whitelist()
def get_available_delivery_notes(doctype, txt, searchfield, start, page_len, filters):
    customer = filters.get("customer")
    if not customer:
        return []

    return frappe.db.sql(f"""
        SELECT dn.name, dn.posting_date
        FROM `tabDelivery Note` dn
        WHERE dn.customer = %s
        AND dn.docstatus = 1
        AND dn.name NOT IN (
            SELECT customer_delivery_note FROM `tabGate Pass`
            WHERE docstatus = 1 AND customer_delivery_note IS NOT NULL
        )
        AND dn.{searchfield} LIKE %s
        ORDER BY dn.posting_date DESC
        LIMIT %s OFFSET %s
    """, (customer, f"%{txt}%", page_len, start))
