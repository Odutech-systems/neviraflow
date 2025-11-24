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

