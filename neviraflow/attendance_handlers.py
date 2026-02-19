from datetime import datetime, date, time, timedelta
import frappe
from frappe.utils import get_datetime, add_days

# Shift clock rules (24h)
SHIFT_CONFIG = {
    "General Shift": (time(8, 0),  time(17, 0)),  # in-window for logs is 08:00–23:00 but attendance end is 17:00
    "SHIFT A":       (time(6, 0),  time(15, 0)),
    "SHIFT B":       (time(14, 0), time(23, 0)),
    "SHIFT C":       (time(23, 0), time(9, 0)),   # crosses midnight
}

def after_insert_action(doc, method = None):
    """
    Runs after an employee checkin is inserted.
    Variable needed: employee_id, employee_name, log_in_type, shift, datetime
    Creates / Updates attendance as per the rules
    """
    employee_id = doc.employee
    employee_name = doc.employee_name
    log_in_type = doc.log_type
    ts = get_datetime(doc.time)
    shift_code = doc.shift or None

    ### Fetch or create attendance per log type
    try:
        if log_in_type == "IN":

            in_time, attendance_date_in = compute_shift_window(doc)

            att = get_attendance(employee_id, attendance_date_in)

            if not att:
                make_attendance(employee_id, attendance_date_in, status="Present", in_time=in_time, shift_code=shift_code)
            if att:
                update_attendance_time(att,log_in_type,in_time)
            
        ### If the log_in_type is OUT, do not try to make an attendance yet, first try to get if there is an attendance the previous day or the current day based on the out time
        # This logic is defined in the compute_shift_window function   
        elif log_in_type == "OUT":
            
            out_time, attendance_date_out = compute_shift_window(doc)

            att = get_attendance(employee_id, attendance_date_out)  ## Try to get the attendance based on the computed attendance date

            if att:
                update_attendance_time(att,log_in_type, out_time)
            if not att:
                att_doc = make_attendance(employee_id, attendance_date_out, status="Present", in_time=out_time, shift_code=shift_code)

    except Exception as e:
        error_context = {
            "employee_id": employee_id,
            "employee_name": employee_name,
            "log_in_type": log_in_type,
            "timestamp": ts.isoformat() if ts else None,
            "attendance_date": ts.date(),
            "error": str(e),
        }
        frappe.log_error(
            message=f"Error in after_insert_action\n\nDetails:\n{frappe.as_json(error_context, indent=2)}\n\nTraceback:\n{frappe.get_traceback()}",
            title="Attendance Processing Failed"
        )
        raise


def compute_shift_window(doc, method=None):
    """
    Computes the shift window based on the check-in time
    Args: 
        ts (datetime): the checkin date-time on the Checkin doctype
        shift_code (str): the employee's shift code

    Returns: 
        attendance_date : attendance date (date)
        attendance_in_time : in_time (datetime)
        attendance_out_time : out_time (datetime)
    """
    
    in_time, out_time, attendance_date = None, None, None
    ts = get_datetime(doc.time)

    if doc.log_type == "IN":
        attendance_date = ts.date()
        in_time = datetime.combine(ts.date(), ts.time())
        return in_time, attendance_date
        
    if doc.log_type == "OUT":
        if (ts.time() > time(0,0)) and (ts.time() < time(10,0)): 
            out_time = datetime.combine(ts.date(), ts.time()) ## Keep the out time as it is
            attendance_date = ts.date() - timedelta(days=1) ## This means that check-out after midnight refer to the previous day's attendance
        else:
            out_time = ts
            attendance_date = ts.date() ## Just the date as it is without adding a day
        return out_time, attendance_date


def get_attendance(employee: str, attendance_date: date):
    """
    This function will get the attendance record for an employee on the specified date.
    """                     
    name = frappe.db.exists("Attendance", 
                            {"employee":employee, 
                            "attendance_date": attendance_date, 
                            "docstatus":("!=",2)})
    
    return frappe.get_doc("Attendance", name) if name else None


def make_attendance(employee_id: str, attendance_date: date, status: str, in_time = None, out_time=None, shift_code=None):
    ## Change the function to accept shift_code as an optional parameter
    attendance_doc = frappe.new_doc("Attendance")
    attendance_doc.update({
        "employee": employee_id,
        "status": status,
        "attendance_date": attendance_date,
        "shift": shift_code,
        "in_time": in_time,
        "out_time": out_time
    })
    attendance_doc.insert(ignore_permissions=True, ignore_if_duplicate=True)
    attendance_doc.submit()
    frappe.db.commit()

    return attendance_doc

def update_attendance_time(attendance, log_type, event_time):
    """
    This function will update the existing attendance, whether its IN/OUT,
    specifically the in_time and out_time
    """
    changed = False

    if log_type == "IN":
        if not attendance.in_time:
            attendance.in_time = event_time
            changed = True
    elif log_type == "OUT":
        if not attendance.out_time or event_time > attendance.out_time:
            attendance.out_time = event_time
            changed = True
    if changed:
        attendance.save(ignore_permissions=True)
        frappe.db.commit()

def get_previous_logtype_and_time(employee_id):
    previous_attendance_query = frappe.db.sql("""
                                SELECT 
                                    employee, 
                                    employee_name, log_type,time FROM `tabEmployee Checkin`
                                    WHERE employee = %s ORDER BY time DESC LIMIT 1      
                                """,(employee_id), as_dict=True)
    if previous_attendance_query:
        previous_log_type = previous_attendance_query[0]["log_type"]
        previous_timestamp = previous_attendance_query[0]["time"]
    return previous_log_type, previous_timestamp






def get_shift_for_employee(employee: str, when_dt: datetime) -> str | None:
    """
    Find the most recent shift that the employee has neem assigned to, if no
    shift is found then use the General Shift
    """

    the_day = when_dt.date()
    row = frappe.db.sql(""" 
            SELECT sa.shift_type 
            FROM `tabShift Assignment` AS sa JOIN (
                    SELECT employee, MAX(creation) AS maxc 
                    FROM `tabShift Assignment` WHERE status = 'Active' GROUP BY employee)
                    x ON x.employee = sa.employee 
            AND x.maxc = sa.creation
            WHERE sa.employee=%s
            AND (sa.start_date IS NULL OR sa.start_date <= %s)
            AND (sa.end_date IS NULL OR sa.end_date >= %s)
            LIMIT 1
            """, (employee, the_day, the_day), as_dict=True)
    if row:
        return row[0]["shift_type"]
    else:
        return "General Shift"
