import frappe

def validate(doc, method):
    frappe.msgprint("Validating Fuel Request")

def on_submit(doc, method):
    frappe.msgprint(f"Submitting Fuel Request {doc.name}")
