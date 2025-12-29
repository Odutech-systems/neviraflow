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

    shift_code = doc.shift 

    shift_start_dt, shift_end_dt, attendance_dt = compute_shift_window(ts, shift_code)

    ### Fetch or create attendance per log type
    try:
        if log_in_type == "IN":
            att = get_attendance(employee_id, attendance_dt)
            late_entry = bool(ts > shift_start_dt)
            in_time = ts
            if not att:
                make_attendance(employee_id, attendance_dt, shift_code, status="Present", late_entry=late_entry, in_time=in_time)
            if att:
                frappe.msgprint("Check in & attendance for today already exists!")
                pass
            
        ### If the log_in_type is OUT, do not try to make an attendance        
        elif log_in_type == "OUT":
            att = get_attendance(employee_id, attendance_dt)
            early_exit = bool(ts < shift_end_dt)
            
            if att:
                att_doc = frappe.get_doc("Attendance",att.name)
                att_doc.early_exit = early_exit
                att_doc.out_time = ts
                att_doc.save(ignore_permissions = True)
                frappe.db.commit()
            if not att:
                att_doc = make_attendance(employee_id, attendance_dt, shift_code, status="Present",early_exit=early_exit)

    except Exception as e:
        error_context = {
            "employee_id": employee_id,
            "employee_name": employee_name,
            "log_in_type": log_in_type,
            "timestamp": ts.isoformat() if ts else None,
            "shift_code": shift_code,
            "attendance_date": attendance_dt if 'attendance_dt' in locals() else None,
            "shift_start_dt": shift_start_dt if 'shift_start_dt' in locals() else None,
            "shift_end_dt": shift_end_dt if 'shift_end_dt' in locals() else None,
            "error": str(e),
        }
        frappe.log_error(
            message=f"Error in after_insert_action\n\nDetails:\n{frappe.as_json(error_context, indent=2)}\n\nTraceback:\n{frappe.get_traceback()}",
            title="Attendance Entry Failed"
        )
        raise

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


def compute_shift_window(doc, method=None):
    """

    After some review, I have decided to abandon the whole idea of having date and time determined by the shift configurations.
    Rather, I will just process the attendance and checkin based on the time and dates I have. This is because of shift C, which starts
    at 22.00 and ends from 7.00 the next day, therefore any checkout from 

    compute_shift_window(ts:datetime, shift_code=None):
    Args: 
        ts (datetime): the checkin date-time on the Checkin doctype
        shift_code (str): the employee's shift code

    Returns: 
        the attendance_date
        the attendance_in_time
        attendance_out_time

    

        elif shift_code == "General Shift":
            start_dt = datetime.combine(ts.date(), s_start)
            end_dt = datetime.combine(ts.date(), s_end)
            attendance_dt = ts.date()
        else:
            start_dt = datetime.combine(ts.date(), s_start)
            end_dt = datetime.combine(ts.date(), s_end)
            attendance_dt = ts.date()
    """
    
    start_dt, end_dt, attendance_dt = None, None, None

    in_time, out_time, attendance_date = None, None, None
    ts = get_datetime(doc.time)

    if doc.log_type == "IN":
        if ts.time() >= time(20,0):
            in_time = datetime.combine(ts.date(), ts.time()) ## get the actual date time as the in_time
            attendance_date = ts.date() ## get the actual attendance date
        
        elif (ts.time() >= time(5,0)) and (ts.time() < time(20,0)):
            ## This category includes shift A, shift B and General Shift
            in_time = datetime.combine(ts.date(), ts.time())
            attendance_date = ts.date()
        return in_time, attendance_date
    
    elif doc.log_type == "OUT":
        if (ts.time > time(1,0)) and (ts.time < time(9,0)):
            out_time = datetime.combine(ts.date() + timedelta(days=1), ts.time()) ##the attendance date is still the same but then the out datetime is the next day
            attendance_date = ts.date()
        else:
            out_time = ts
            attendance_date = ts.date() ## Just the date as it is without adding a day
        return out_time, attendance_date

    
def get_attendance(employee: str, attendance_date: date):
    name = frappe.db.exists("Attendance", {"employee":employee, "attendance_date": attendance_date, "docstatus":("!=",2)})
    return frappe.get_doc("Attendance", name) if name else None

def make_attendance(employee_id: str, attendance_date: date, shift_code: str, status: str,late_entry = 0,early_exit = 0, in_time = None):
    attendance_doc = frappe.new_doc("Attendance")
    attendance_doc.update({
        "employee": employee_id,
        "status": status,
        "attendance_date": attendance_date,
        "shift": shift_code,
        "late_entry": late_entry,
        "early_exit": early_exit,
        "in_time": in_time
    })
    attendance_doc.insert(ignore_permissions=True, ignore_if_duplicate=True)
    attendance_doc.submit()
    frappe.db.commit()
