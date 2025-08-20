from datetime import datetime, date, time, timedelta
import frappe
from frappe.utils import get_datetime

# Shift clock rules (24h)
SHIFT_CONFIG = {
    "General Shift": (time(8, 0),  time(17, 0)),  # in-window for logs is 08:00–23:00 but attendance end is 17:00
    "SHIFT A":       (time(6, 0),  time(15, 0)),
    "SHIFT B":       (time(14, 0), time(23, 0)),
    "SHIFT C":       (time(23, 0), time(7, 0)),   # crosses midnight
}
def normalize_shift_code(name: str) -> str:
    n = (name or "").strip().upper()
    for code in ("GENERAL","A","B","C"):
        if code == n or n.endswith(f"{code}") or n.startswith(f"SHIFT {code}"):
            return code
    return "GENERAL"


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

    ##shift = doc.shift
    ##shift_start = doc.shift_start
    ##shift_end = doc.shift_end

    shift_code = get_shift_for_employee(employee_id, ts)
    shift_start_dt, shift_end_dt, attendance_dt = compute_shift_window(ts, shift_code)

    ### Fetch or create attendance per log type
    if log_in_type == "IN":
        att = get_attendance(employee_name, attendance_dt)
        if not att:
            att = make_attendance(employee_id, employee_name, attendance_dt, shift_code, status = "Present")
            att.late_entry = bool(ts > shift_start_dt)
            att.submit()
    elif log_in_type == "OUT":
        att = get_attendance(employee_name, attendance_dt)
        if not att:
            att = make_attendance(employee_id, employee_name, attendance_dt, shift_code, status = "Present")
            att.early_exit = bool(ts < shift_end_dt)
            att.submit()
        else:
            pass

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


def compute_shift_window(ts:datetime, shift_code: str):
    """
    Return the shift_start_dt, shift_end_dt, attendance_date for the checkin timestamp and shift.
    Shift C spans 23:00 -> 07:00 next day and is assigned to the previous day if time is between 00:00 - 06:59
    """
    s_start, s_end = SHIFT_CONFIG[shift_code]
    if shift_code != "C": 
        start_dt = datetime.combine(ts.date(), s_start)
        end_dt = datetime.combine(ts.date(), s_end)
        ### The general shift allows logging of time even after 23:00
        if shift_code == "GENERAL" and ts.time() <= time(23,0): ## ts.time() > time(23,0)
            pass
        return start_dt, end_dt, ts.date()
    
    ## Review this section of the code accordingly
    if ts.time() >= time(23,0):
        start_dt = datetime.combine(ts.date(), time(23,0))
        end_dt = datetime.combine(ts.date() + timedelta(days=1), time(7,0))
        attendance_dt = ts.date()

    elif ts.time() < time(7,0):
        start_dt = datetime.combine(ts.date() - timedelta(days=1), time(23,0))
        end_dt = datetime.combine(ts.date(), time(7,0))
        attendance_dt = ts.date() - timedelta(days=1)
    
    else:
        start_dt = datetime.combine(ts.date(), time(23,0)) - timedelta(days =1)
        end_dt = datetime.combine(ts.date(), time(7,0))
        attendance_dt = ts.date()
    return start_dt, end_dt, attendance_dt

def get_attendance(employee: str, attendance_date: date):
    name = frappe.db.exists("Attendance", {"employee":employee, "attendance_date": attendance_date, "docstatus":("!=",2)})
    return frappe.get_doc("Attendance", name) if name else None

def make_attendance(employee_id: str, attendance_date: date, shift_code: str, status: str):
    attendance_doc = frappe.new_doc("Attendance")
    attendance_doc.update({
        "employee": employee_id,
        "status": status,
        "attendance_date": attendance_date,
        "shift": shift_code
    })
    attendance_doc.insert(ignore_permissions=True, ignore_if_duplicate=True)
    attendance_doc.submit()
    frappe.db.commit()
    


