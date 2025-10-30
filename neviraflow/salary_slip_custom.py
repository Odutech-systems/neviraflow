from frappe.utils import datetime, flt
import frappe



def compute_absenteeism_deduction(doc, method = None):
    """
    Computes absenteeism deduction and adjusts the Basic Salary component in the earnings table.
    This function shoud be executed on the validate hook of the Salary Slip doctype.
    """
    absent_days = flt(doc.absent_days)
    working_days = flt(doc.total_working_days)
    gross_salary  = flt(doc.base_gross_pay)

    if absent_days <= 0 or working_days <= 0:
        frappe.msgprint(f"Skipping absenteeism calculation: Absent days {absent_days} or Working days {working_days} is zero")
        return

    basic_salary_row = None 
    initial_base_amount = 0

    ## find the basic amount in the earnings table
    for row in doc.earnings:
        if row.salary_component == "Basic Salary":
            basic_salary_row = row
            ## Store the initial base salary for later reference
            initial_base_amount  = flt(row.amount)
            break
    if basic_salary_row:
        try:
            ## compute the daily pay
            daily_pay = gross_salary / working_days ## Use the initial_base_amount instead of the gross salary amount ?
            absent_days_deduction = daily_pay * absent_days
            ## Compute new_basic_salary i.e Original amount - absent_days_deduction

            new_basic_salary_amount = initial_base_amount - absent_days_deduction

            ## Ensure the amount is not negative
            if new_basic_salary_amount < 0:
                new_basic_salary_amount = 0
                absent_days_deduction = initial_base_amount ## The deduction is capped
            
            ## update the child table row amount
            basic_salary_row.amount = new_basic_salary_amount

            ## Compute the new total_deductions
            doc.total_deduction = doc.total_deduction + absent_days_deduction
            doc.net_pay = doc.base_gross_pay - doc.total_deductions

            ## Store the calculated fields on custom fields on the doctype
            doc.custom_daily_pay = daily_pay
            doc.custom_absent_days_deduction = absent_days_deduction
            frappe.msgprint(f"Absenteeism deduction of {absent_days_deduction: ,.2f} applied to Basic Salary.")

        except Exception as e:
            frappe.throw(f"Error during new basic salary computation: {e}")
    else:
        frappe.msgprint("Warning: Could not find 'Basic Salary' component in the earnings table to apply deductions.",
                        alert=True,indicator='red',
                        title='Deduction calculation error')



