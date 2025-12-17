from frappe.utils import flt
import frappe

def set_daily_rate(doc, method=None):
    """
    Compute the employee's daily salary amount based on the employee's 
    CTC. This is to be done before saving the employee docType
    """
    if doc.ctc and flt(doc.ctc) > 0:
        doc.custom_daily_salary_rate = flt(doc.ctc) / 30
    else:
        doc.custom_daily_salary_rate = 0

def validate_employee_ctc(doc, method=None):
    """
    Validate that the CTC is a positive number
    """
    if doc.ctc and flt(doc.ctc) < 0:
        frappe.throw("CTC cannot be negative")

def update_all_daily_rates():
    """
    Bulk update the daily salary rate for all employees
    """
    employees = frappe.get_all("Employee", filters={"ctc": [">",0]}, 
                               fields=["name","ctc"])
    updated_count = 0
    for employee in employees:
        try:
            daily_rate = flt(employee.ctc) / 30
            frappe.db.set_value("Employee", employee.name, "custom_daily_salary_rate", daily_rate)
            updated_count += 1
        except Exception as e:
            frappe.log_error(f"Error in updating the employee {employee.name}: {str(e)}")
    frappe.db.commit()
    print(f"Updated the daily salary rate for {updated_count} employees")