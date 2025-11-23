from frappe.utils import flt
import frappe

def set_daily_rate(doc, method=None):
    """
    Compute the employee's daily salary amount based on the employee's 
    CTC. This is to be done before saving the employee docType
    """
    if doc.ctc and (flt.ctc) > 0:
        doc.daily_salary_rate = doc.ctc / 30
    else:
        doc.ctc = 0

def validate_employee_ctc(doc, method=None):
    """
    Validate that the CTC is a positive number
    """
    if doc.ctc and flt(doc.ctc) < 0:
        frappe.throw("CTC cannot be negative")

