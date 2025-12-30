from frappe.utils import datetime, flt
import frappe
import json
from frappe.utils import getdate, get_first_day, get_last_day
from frappe.query_builder import DocType
from frappe.query_builder.functions import Count

def get_absent_days_sql(employee, start_date, end_date):
    """
    Use SQL to get the number of absent days, parse the employee id, start date and end date
    """
    absent_sql =   """
            SELECT COUNT(name) AS absent_days FROM `tabAttendance` WHERE docstatus = 1
            AND status = 'Absent' 
            AND employee = %s
            AND attendance_date BETWEEN %s AND %s
            """
    result = frappe.db.sql(absent_sql,(employee, start_date, end_date), as_dict=True)
    return result[0]['absent_days'] if result else 0

def get_worked_days_on_holidays(employee):
    worked_days_sql = """
                        SELECT
                            employee,
                            COUNT(name) AS worked_days
                            FROM
                            `tabAttendance`
                            WHERE
                            docstatus = 1
                            AND attendance_date IN ('2025-12-12', '2025-12-25', '2025-12-26')
                            AND employee = %s
                            GROUP BY
                            employee"""
    res = frappe.db.sql(worked_days_sql, (employee), as_dict=True)
    return res[0]['worked_days'] if res else 0


def get_absent_days(employee, start_date, end_date):
    """
    Get the absent days marked for the emplyee in the given period using frappe.qb
    """
    Attendance = DocType("Attendance")
    query = (frappe.qb.from_(Attendance)
             .select(Count(Attendance.name).as_('absent_days'))
             .where(
                (Attendance.docstatus == 1)
                & (Attendance.employee == employee)
                & (Attendance.status == "Absent")
                & (Attendance.attendance_date >= start_date)
                & (Attendance.attendance_date <= end_date)
                )
            )
    result = query.run()

    return result[0][0] if result else 0



def before_submit_salary_structure_assignment(doc, method):
    """
    Compute base amount based on the absent days and prorated salary
    """
    payroll_start_date = doc.from_date
    payroll_end_date = get_last_day(doc.from_date)  ### instead of using doc.to_date which does not exist
    employee = frappe.get_doc("Employee", doc.employee)

    ### Extract the employee details  to get the value of ctc & daily rate from the employee directly
    if employee.ctc:
        daily_rate = employee.custom_daily_salary_rate
        doc.custom_daily_rate = daily_rate                
    else:
        frappe.throw(f"CTC not set for employee {doc.employee}")

    joining_date = employee.date_of_joining
    payroll_start = getdate(payroll_start_date)

    if joining_date > get_first_day(payroll_start_date):
        doc.custom_is_prorated_salary = 1        
        
        ### Calculate the number of worked days from the joining date to the end of the month
        if joining_date > payroll_start:
            start_date = joining_date
        else:
            start_date = payroll_start
        end_date = get_last_day(payroll_start)
        worked_days = (end_date - start_date).days + 1   ## Must include both ends
        doc.custom_worked_days = max(0, worked_days)    

        ### Calculate the prorated amount
        doc.custom_prorated_amount = daily_rate * worked_days
    else:
        doc.custom_is_prorated_salary = 0
        doc.custom_worked_days = 30
        doc.custom_prorated_amount = employee.ctc
    
    absent_days = get_absent_days(doc.employee, payroll_start_date, payroll_end_date)
    doc.custom_absent_days = absent_days      

    ### Compute the absent days deductions
    doc.custom_absent_days_deduction = daily_rate * absent_days

    ## worked_days on holidays
    overtime_days = get_worked_days_on_holidays(doc.employee)
    doc.custom_overtime_amount = flt(overtime_days * daily_rate)
    doc.custom_holiday_days_worked = overtime_days


    overtime_amount = doc.custom_overtime_amount or 0

    if doc.custom_is_prorated_salary:
        base_amount = doc.custom_prorated_amount  + overtime_amount - doc.custom_absent_days_deduction
    else:
        base_amount = employee.ctc + overtime_amount - doc.custom_absent_days_deduction
    doc.base = base_amount


## Set the absent days deduction on the salary slip as well
def compute_and_set_absent_days(doc, method=None):
    employee_id = doc.employee
    start_date = doc.start_date
    end_date = doc.end_date
    new_absent_days = get_absent_days(employee_id, start_date, end_date)

    if new_absent_days > 0:
        doc.custom_computed_absent_days = new_absent_days
        daily_rate = doc.custom_daily_pay
        absent_days_deduction = new_absent_days * daily_rate 
        doc.custom_absent_days_deduction = absent_days_deduction
    else:
        doc.custom_absent_days_deduction = 0                                                                         