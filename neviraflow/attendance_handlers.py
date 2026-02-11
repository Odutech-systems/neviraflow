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
                frappe.msgprint("Check in & attendance for today already exists!")
                pass
            
        ### If the log_in_type is OUT, do not try to make an attendance yet, first try to get if there is an attendance the previous day or the current day based on the out time
        # This logic is defined in the compute_shift_window function   
        elif log_in_type == "OUT":
            
            out_time, attendance_date_out = compute_shift_window(doc)

            # att = get_in_attendance(employee_id, ts.date())

            att = get_in_attendance(employee_id, attendance_date_out)  ## Try to get the attendance based on the computed attendance date

            if att:
                att_doc = frappe.get_doc("Attendance",att.name)
                att_doc.out_time = out_time
                att_doc.save(ignore_permissions = True)
                frappe.db.commit()
            if not att:
                att_doc = make_attendance(employee_id, attendance_date_out, status="Present", out_time=out_time, shift_code=shift_code)

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
            title="Attendance Entry Failed"
        )
        raise


def compute_shift_window(doc, method=None):
    """

    After some review, I have decided to abandon the whole idea of having date and time determined by the shift configurations.
    Rather, I will just process the attendance and checkin based on the time and dates I have. This is because of shift C, which starts
    at 22.00 and ends from 7.00 the next day, therefore any checkout from 00.00 to 07.00 will have to be considered as part of the previous day attendance.

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
        if ts.time() >= time(20,0): ## why did I put >= here? I think if someone checks in past 20.00 it should part of shift C
            in_time = datetime.combine(ts.date(), ts.time()) ## get the actual date time as the in_time
            attendance_date = ts.date() ## get the actual attendance date
        
        elif (ts.time() >= time(2,0)) and (ts.time() < time(20,0)):  
            # But is someone checks in between 02.00 and 20.00 then  it should be part of shift A, shift B or General Shift,
            # drivers for example have a tendecy to checkin very early in the morning
            
            in_time = datetime.combine(ts.date(), ts.time())
            attendance_date = ts.date()
        return in_time, attendance_date
    
    elif doc.log_type == "OUT":
        if (ts.time() > time(2,0)) and (ts.time() < time(10,0)): 
            # The question remains to be: what is the appropriate overlap between shift C and shift A ?
            # If someone checks out between 2 am and 9 am, basically that means that they are checking out from the previous day's shift. 
            # So it means that the attendance date is the current date, but we should look for the previous day's attendance record and update the out time of that attendance record
            # out_time = datetime.combine(ts.date() + timedelta(days=1), ts.time()) ##the attendance date is still the same but then the out datetime is the next day
            
            out_time = datetime.combine(ts.date(), ts.time()) ## Keep the out time as it is
            
            # attendance_date = ts.date()

            ## Another idea here is to subract one day from the attendance date, so that the out time is still the same but the attendance date is the previous day
            attendance_date = ts.date() - timedelta(days=1) ## This means that we are updating the previous day's attendance record but will update the out_time to the current out time
        else:
            out_time = ts
            attendance_date = ts.date() ## Just the date as it is without adding a day
        return out_time, attendance_date


def get_attendance(employee: str, attendance_date: date):
    name = frappe.db.exists("Attendance", 
                            {"employee":employee, 
                            "attendance_date": attendance_date, 
                            "docstatus":("!=",2)})
    
    return frappe.get_doc("Attendance", name) if name else None

def get_in_attendance(employee: str, attendance_date: date):
    name = frappe.db.exists("Attendance", {
        "employee": employee,
        "attendance_date": attendance_date,
        "docstatus": ["!=",2],
        "in_time":["is","set"],
        "out_time":["is","not set"]  ### This passes the match, because we are looking for an attendance that has in_time set but out_time is not set
    })
    return frappe.get_doc("Attendance",name) if name else None


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
