import frappe
from frappe.utils import now_datetime, getdate, get_time, add_to_date
from datetime import datetime, time, timedelta
from frappe import _


@frappe.whitelist(allow_guest=True)
def mark_absentees():
    """
    Background job to mark absent employees 
    The job runs daily at 10.00 AM to mark the attendance (absent and on leave) for the previous day
    """
    try:
        previous_day = add_to_date(getdate(), days=-1)
        #previous_day_str = '22-08-2025'
        #previous_day = datetime.strptime(previous_day_str,"%d-%m-%Y")
        #previous_day = previous_day.date()

        ## Get the list of active employees, the idea is that I want to move to sets eventually but for now I will just start with a list object
        active_employees = get_active_employees()

        ## Get the employees with a shift assignment
        employees_with_assignments = get_employees_with_shift_assignments()

        ## Get the employees who have attendance the previous day
        employees_with_attendance = get_employee_with_attendance(previous_day)

        ## Get the employees to mark as absent, i.e they have a shift assignment but do not have attendance
        employees_to_mark_absent = []
        for emp in employees_with_assignments:
            if emp not in employees_with_attendance:
                employees_to_mark_absent.append(emp)

        ## Mark absent employees
        for employee_id in employees_to_mark_absent:
            try:
                ## Check if the employee is on leave
                shift_type = get_employee_shift(employee_id)
                ## Check if the employee is on leave, the HR module auto-creates approved leaves on attendance list, so no need to create them ourselves
                on_leave = check_employee_on_leave(employee_id, previous_day)
                status = "On Leave" if on_leave else "Absent"
                attendance = frappe.new_doc("Attendance")
                attendance.update({
                    "employee": employee_id,
                    "status": status,
                    "attendance_date": previous_day,
                    "shift": shift_type
                })
                if not on_leave:
                    attendance.insert(ignore_permissions=True, ignore_if_duplicate=True)
                    attendance.submit()
                    frappe.db.commit()
                else:
                    frappe.msgprint(f"Employee {employee_id} is on leave, leaves are marked automatically on Attendance list once approved")
            except Exception as e:
                frappe.log_error(frappe.get_traceback(),f"Error marking attendance for employee {employee_id}")
                frappe.db.rollback()
        frappe.msgprint(_(f"Absentee marking for {previous_day} completed successfully."))
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Absentee marking Job Error")
        frappe.msgprint(_("Error in absentee marking job. Please check error logs for more information."))


def get_active_employees():
    """
    Get a list/set of active employees in the database
    """
    active_employees = frappe.get_all("Employee",filters={"status":"Active"}, fields=["name"])
    return [emp.name for emp in active_employees]

def get_employees_with_shift_assignments():
    """
    Get the employees with shift assignments
    """
    assignments = frappe.get_all("Shift Assignment",
                                 filters = {"status": "Active"},fields=["employee","shift_type"], distinct=True)
    
    return [assignment.employee for assignment in assignments]

def get_employee_with_attendance(date):
    """
    Get employees who already have an attendance on the previous day
    """
    attendances = frappe.get_all("Attendance",
                                 filters={"attendance_date": date,
                                          "docstatus": ["!=",2]},
                                fields = ["employee"],
                                distinct=True)

    return [att.employee for att in attendances]

def get_employee_shift(employee):
    """
    Get the shift type for an employee, just one shift only
    """
    shift_assignment = frappe.get_all("Shift Assignment",
                            filters={
                                "employee": employee,
                                "status": "Active"
                            },
                            fields = ["shift_type"],
                            limit =1
                            )
    return shift_assignment[0].shift_type if shift_assignment else None


def check_employee_on_leave(employee, date):
    """
    Check if the employee is on leave on the given date
    """
    leave_applications = frappe.get_all("Leave Application",
                                filters = {
                                    "employee": employee,
                                    "from_date": ["<=",date],
                                    "to_date": [">=", date],
                                    "status": "Approved"
                                }, limit = 1)
    return bool(leave_applications)
