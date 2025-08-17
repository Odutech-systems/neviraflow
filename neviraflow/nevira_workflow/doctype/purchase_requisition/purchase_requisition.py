# Copyright (c) 2025, Victor Mandela and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

class PurchaseRequisition(Document):
    def before_insert(self):
        self.requisition_no = generate_custom_requisition_no()

    def on_submit(self):
        create_material_request_from_requisition(self)

def generate_custom_requisition_no():
    today = now_datetime()
    date_str = today.strftime("%d%m%y")  # DDMMYY
    prefix = f"NML-PRQ-{date_str}"

    last = frappe.db.sql(f"""
        SELECT requisition_no
        FROM `tabPurchase Requisition`
        WHERE requisition_no LIKE %s
        ORDER BY creation DESC
        LIMIT 1
    """, (f"{prefix}%",), as_dict=True)

    if last:
        last_seq = int(last[0]["requisition_no"][-3:])
        new_seq = last_seq + 1
    else:
        new_seq = 1

    return f"{prefix}{str(new_seq).zfill(3)}"

@frappe.whitelist()
def create_material_request_from_requisition(pr):
    if isinstance(pr, str):
        pr = frappe.get_doc("Purchase Requisition", pr)

    mr = frappe.new_doc("Material Request")
    mr.material_request_type = "Purchase"
    mr.requisition_number = pr.requisition_no
    mr.requisition_type = pr.requisition_type
    mr.set_warehouse = pr.set_default_warehouse
    mr.transaction_date = pr.requisition_date
    mr.schedule_date = pr.date_required or pr.requisition_date

    for item in pr.items:
        mr.append("items", {
            "item_code": item.item_code,
            "qty": item.quantity,  # corrected field name
            "warehouse": pr.set_default_warehouse,
            "schedule_date": pr.date_required or pr.requisition_date
        })

    mr.insert(ignore_permissions=True)
    mr.submit()

    frappe.msgprint(f"Material Request <a href='/app/material-request/{mr.name}' target='_blank'>{mr.name}</a> created.")
