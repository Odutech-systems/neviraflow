from __future__ import annotations

from typing import Optional
from datetime import datetime, timedelta

import frappe
import csv
import os
from frappe import _
from frappe.model.naming import make_autoname
from frappe.utils.pdf import get_pdf
import yaml
from frappe.utils import today
from frappe.utils import nowdate, nowtime, date_diff, time_diff_in_hours, getdate, get_datetime





def assign_export_metadata(doc, method):
    # Set export_series if needed
    if not doc.get("export_series"):
        linked_export_series = None

        if doc.doctype == "Sales Order":
            if hasattr(doc, "quotation") and doc.quotation:
                linked_export_series = frappe.db.get_value("Quotation", doc.quotation, "export_series")

        elif doc.doctype == "Delivery Note":
            for item in doc.items:
                if item.against_sales_order:
                    linked_export_series = frappe.db.get_value("Sales Order", item.against_sales_order, "export_series")
                    if linked_export_series:
                        break

        elif doc.doctype == "Sales Invoice":
            for item in doc.items:
                if item.delivery_note:
                    linked_export_series = frappe.db.get_value("Delivery Note", item.delivery_note, "export_series")
                    if linked_export_series:
                        break
                elif item.sales_order:
                    linked_export_series = frappe.db.get_value("Sales Order", item.sales_order, "export_series")
                    if linked_export_series:
                        break

        if not linked_export_series and doc.get("taxes_and_charges") == "Rest of World Tax - NML":
            linked_export_series = make_autoname("NEV/EXP/P.####")

        if linked_export_series:
            doc.export_series = linked_export_series

    # Set shipping_country if needed
    if not doc.get("shipping_country") and doc.get("customer"):
        customer_country = frappe.db.get_value("Customer", doc.customer, "shipping_country")
        doc.shipping_country = customer_country or "Kenya"



@frappe.whitelist()
def update_clearance_date(docname, new_date):
    doc = frappe.get_doc("PDC Booking and Clearance", docname)

    if doc.docstatus != 1:
        frappe.throw("Only submitted documents can be updated.")

    if not doc.allow_clearance_date_update():
        frappe.throw(f"Not allowed to change Clearance Date after submission when status is {doc.clearance_status}.")

    doc.db_set("clearance_date", new_date)
    frappe.msgprint(f"Clearance Date updated to {new_date}")



@frappe.whitelist()
def mark_pdc_cleared(docname):
    _update_pdc_status(docname, "Cleared")


@frappe.whitelist()
def mark_pdc_bounced(docname, charge_amount=None, charge_account=None):
    if not charge_amount or not charge_account:
        frappe.throw("Charge amount and charge account are required to mark as Bounced.")

    _update_pdc_status(docname, "Bounced", charge_amount=float(charge_amount), charge_account=charge_account)


@frappe.whitelist()
def mark_pdc_cancelled(docname):
    _update_pdc_status(docname, "Cancelled")


def _update_pdc_status(docname, new_status, charge_amount=None, charge_account=None):
    doc = frappe.get_doc("PDC Booking and Clearance", docname)

    if doc.docstatus != 1:
        frappe.throw("Only submitted documents can be modified.")

    if doc.clearance_status in ["Cleared", "Bounced", "Cancelled"]:
        frappe.throw(f"PDC already marked as {doc.clearance_status}. Cannot change to {new_status}.")

    if new_status == "Cleared":
        doc.mark_as_cleared()

    elif new_status == "Bounced":
        if not charge_amount or not charge_account:
            frappe.throw("Bounce charge details are required.")
        doc.mark_as_bounced(charge_amount=charge_amount, charge_account=charge_account)

    elif new_status == "Cancelled":
        doc.mark_as_cancelled()

    frappe.msgprint(f"PDC marked as {new_status}.")



@frappe.whitelist()
def get_work_order_by_workstation(workstation):
    work_orders = frappe.get_all("Work Order", filters={
        "status": ["in", ["Not Started", "In Process"]]
    }, fields=["name"])

    for wo in work_orders:
        operations = frappe.get_all("Work Order Operation", {
            "parent": wo.name,
            "workstation": workstation
        })
        if operations:
            return wo.name
    return ""


@frappe.whitelist()
def get_bulk_raw_material_from_bom(item_code=None):
    if not item_code:
        frappe.throw("Item Code is required")

    bom_name = frappe.db.get_value("BOM", {
        "item": item_code,
        "is_active": 1,
        "is_default": 1
    }, "name")

    if not bom_name:
        return None

    bom_doc = frappe.get_doc("BOM", bom_name)

    for row in bom_doc.items:
        item_group = frappe.db.get_value("Item", row.item_code, "item_group")
        if item_group == "Raw Materials - BULK":
            return row.item_code

    return None


@frappe.whitelist()
def handle_pick_list_and_qty_patch(doc, method):
    # PATCH 1: Ensure all Pick List locations inherit the parent warehouse
    if doc.doctype == "Pick List":
        for loc in doc.locations:
            if not loc.warehouse and doc.parent_warehouse:
                loc.warehouse = doc.parent_warehouse

    # PATCH 2: On Delivery Note created from Pick List, map key values
    elif doc.doctype == "Delivery Note" and doc.pick_list:
        # Map customer from Pick List to Delivery Note
        pick_list_customer = frappe.db.get_value("Pick List", doc.pick_list, "customer")
        if pick_list_customer:
            doc.customer = pick_list_customer

        for item in doc.items:
            # Try to get picked_qty from the linked Pick List Item
            if hasattr(item, "pick_list_item") and item.pick_list_item:
                picked_qty = frappe.db.get_value("Pick List Item", item.pick_list_item, "picked_qty")
                if picked_qty:
                    item.qty = picked_qty
                    item.bags_input = picked_qty

            # Transfer warehouse from Pick List if not already set
            if not item.warehouse and doc.set_warehouse:
                item.warehouse = doc.set_warehouse

            item.set("__readonly", True)
 
            
# Endpoint to accept payloads from the weighbridge software and ensure the
# Vehicle exists, then create/submit a Weighbridge Management document.

SESSION_LOOKBACK_HOURS = 12  # consider open sessions in the last N hours

@frappe.whitelist(allow_guest=False)
def ingest_weighbridge_event(**kwargs):
    data = frappe._dict(kwargs or {})

    vehicle_no = (
        (data.get("vehicle_registration_number") or data.get("vehicle_no") or data.get("vehicle") or "")
        .strip()
        .upper()
    )
    driver_name = (data.get("driver_name") or "").strip() or None
    external_ref = (data.get("external_ref") or "").strip() or None

    # Parse weights
    try:
        first_weight = float(data.get("first_weight"))
        second_weight = float(data.get("second_weight"))
    except Exception:
        frappe.throw(_("first_weight and second_weight must be numeric"))

    if not vehicle_no:
        frappe.throw(_("vehicle_registration_number / vehicle_no is required"))
    if second_weight <= first_weight:
        frappe.throw(_("second_weight must be greater than first_weight"))

    if external_ref:
        existing = frappe.db.get_value(
            "Weighbridge Management", {"remarks": ("like", f"%ext:{external_ref}%")}, "name"
        )
        if existing:
            return {"ok": True, "docname": existing, "status": "duplicate_ignored"}

    vehicle_name = _get_or_create_vehicle(vehicle_no)

    # Check if there is an OPEN multi-weighing session for this vehicle
    open_prev = _find_open_session_ticket(vehicle_name)

    if open_prev:
        # Create the next ticket in the session; carry-forward first_weight from previous second_weight
        session_id = open_prev.get("weighing_session_id") or open_prev.get("name")
        next_no = (open_prev.get("current_weighing_no") or 1) + 1
        total_expected = open_prev.get("total_weighings_expected")
        prev_second = float(open_prev.get("second_weight") or 0)

        doc = frappe.get_doc({
            "doctype": "Weighbridge Management",
            "vehicle_registration_number": vehicle_name,
            "driver_name": driver_name,
            # override first_weight using previous second_weight
            "first_weight": prev_second,
            "second_weight": second_weight,
            "has_multiple_weights": 1,
            "total_weighings_expected": total_expected,
            "current_weighing_no": next_no,
            "weighing_session_id": session_id,
            "previous_ticket": open_prev.get("name"),
            # keep item_type same as previous by default (user can change later)
        })
        doc.insert(ignore_permissions=True)
        doc.submit()

        # Mark final if we reached expected count
        if total_expected and int(next_no) >= int(total_expected):
            doc.db_set("is_final_weighing", 1)

        # store the device-provided raw first_weight for audit
        try:
            bits = [
                f"veh:{vehicle_no}",
                f"fw_raw:{first_weight}",
                f"fw:{prev_second}",
                f"sw:{second_weight}",
            ]
            if external_ref:
                bits.append(f"ext:{external_ref}")
            doc.db_set("remarks", " | ".join(bits))
        except Exception:
            pass

        return {"ok": True, "docname": doc.name, "session": session_id, "no": next_no}

    # No open session -> create a fresh single ticket (or the first of a session if user later flags it)
    doc = frappe.get_doc({
        "doctype": "Weighbridge Management",
        "vehicle_registration_number": vehicle_name,
        "driver_name": driver_name,
        "first_weight": first_weight,
        "second_weight": second_weight,
        # current_weighing_no begins at 1 by default at the DocType level
    })

    doc.insert(ignore_permissions=True)
    doc.submit()

    try:
        bits = [f"veh:{vehicle_no}", f"fw:{first_weight}", f"sw:{second_weight}"]
        if external_ref:
            bits.append(f"ext:{external_ref}")
        # If clerk sets has_multiple later, this ticket will become session head (weighing_session_id=doc.name)
        doc.db_set("remarks", " | ".join(bits))
    except Exception:
        pass

    return {"ok": True, "docname": doc.name}


def _get_or_create_vehicle(vehicle_no: str) -> str:
    existing = frappe.db.get_value("Vehicle", {"license_plate": vehicle_no}, "name")
    if existing:
        return existing
    if frappe.db.exists("Vehicle", vehicle_no):
        return vehicle_no

    vehicle = frappe.get_doc({
        "doctype": "Vehicle",
        "license_plate": vehicle_no,
    })
    vehicle.insert(ignore_permissions=True)
    return vehicle.name


# --- Session-aware multiple-weighing support ---
# See commentary in original source for behaviour details

def _find_open_session_ticket(vehicle_name: str) -> Optional[dict]:
    """Return the latest submitted WM ticket (as dict) that is part of an open multi-weighing session
    for this vehicle, or None if not found. Open means: has_multiple_weights=1 AND is_final_weighing=0.
    We also limit by a recent time window to avoid stale sessions.
    """
    candidates = frappe.get_all(
        "Weighbridge Management",
        filters={
            "vehicle_registration_number": vehicle_name,
            "docstatus": 1,
            "has_multiple_weights": 1,
            "is_final_weighing": 0,
        },
        fields=[
            "name",
            "creation",
            "weighing_session_id",
            "current_weighing_no",
            "total_weighings_expected",
            "second_weight",
        ],
        order_by="creation desc",
        limit=5,
    )
    if not candidates:
        return None

    now = datetime.utcnow()
    for row in candidates:
        try:
            created = row.get("creation")
            # Frappe returns string timestamps; parse defensively
            if isinstance(created, str):
                created_ts = datetime.strptime(created.split(".")[0], "%Y-%m-%d %H:%M:%S")
            else:
                created_ts = created
            if created_ts and (now - created_ts) <= timedelta(hours=SESSION_LOOKBACK_HOURS):
                if row.get("weighing_session_id") and row.get("total_weighings_expected"):
                    return row
        except Exception:
            continue
    return None



# Endpoint to export submitted documents as PDFs with metadata for Paperless-ngx
def export_submitted_docs():
    consume_dir = "/home/administrator/docker-apps/paperless/data/consume"
    os.makedirs(consume_dir, exist_ok=True)

    doctypes = {
        "Sales Invoice": {
            "tag": "Sales Invoice",
            "party_field": "customer"
        },
        "Delivery Note": {
            "tag": "Delivery Note",
            "party_field": "customer"
        },
        "Purchase Order": {
            "tag": "Purchase Order",
            "party_field": "supplier"
        }
    }

    for doctype, config in doctypes.items():
        docs = frappe.get_all(doctype, filters={"docstatus": 1}, fields=["name", "posting_date"])

        for doc in docs:
            try:
                # Load document
                obj = frappe.get_doc(doctype, doc.name)

                # Generate PDF
                html = frappe.get_print(doctype, doc.name)
                pdf = get_pdf(html)

                # Metadata
                date = str(getattr(obj, "posting_date", "UnknownDate"))
                party = getattr(obj, config["party_field"], "UnknownParty").replace(" ", "_")
                tag = config["tag"]
                filename_base = f"{tag}_{doc['name']}_{party}_{date}"

                pdf_path = os.path.join(consume_dir, f"{filename_base}.pdf")
                yaml_path = os.path.join(consume_dir, f"{filename_base}.metadata.yaml")

                if not os.path.exists(pdf_path):
                    # Write PDF
                    with open(pdf_path, "wb") as f:
                        f.write(pdf)

                    # Write YAML metadata
                    metadata = {
                        "title": f"{tag} {doc['name']}",
                        "tags": [tag],
                        "correspondent": party
                    }

                    with open(yaml_path, "w") as f:
                        yaml.dump(metadata, f, default_flow_style=False)

                    print(f"Exported {doctype}: {doc['name']}")
                else:
                    print(f"Skipped (already exists): {filename_base}.pdf")

            except Exception as e:
                frappe.log_error(f"{doctype} {doc['name']} export failed", str(e))


####### THESE FUNCTIONS ARE ONLY USED AS BACKUPS TO THE MAIN api.py file functions incase the developer decides to overwrite them


def _get_previous_logtype_and_time(employee_id):
    """
    Get the previous employee's log type
    """
    previous_attendance_query = frappe.db.sql("""
                                SELECT 
                                    employee, 
                                    employee_name, log_type, time FROM `tabEmployee Checkin`
                                    WHERE employee = %s AND log_type 
                                    IS NOT NULL ORDER BY time DESC LIMIT 1      
                                """,(employee_id,), as_dict=True)
    if previous_attendance_query:
        previous_log_type = previous_attendance_query[0]["log_type"]
        previous_timestamp = previous_attendance_query[0]["time"]
        return previous_log_type, previous_timestamp
    else:
        return None, None


def _evaluate_and_infer_logtype(employee, ts):
    
    previous_log_type, previous_log_time = _get_previous_logtype_and_time(employee)

    if not previous_log_time or not previous_log_type:
        return "IN"

    current_date = getdate(ts)
    current_datetime = get_datetime(ts)
    last_checkin_date = getdate(previous_log_time)

    time_difference_hours = time_diff_in_hours(current_datetime, previous_log_time)
    days_difference = date_diff(current_date, last_checkin_date)

    if previous_log_type == "IN":
        if current_date == last_checkin_date:
            return "OUT"

        elif (days_difference == 1) and (time_difference_hours <= 15): ## Best case is that in Shift C, someone has until 8am to checkout
            return "OUT"


        elif (days_difference == 1) and (time_difference_hours >= 16): ### Some one forgot to checkout the previous day hence above 16hrs, so this considered as a new checkin
            return "IN"

        elif days_difference > 1:
           return "IN"

    elif previous_log_type == "OUT":
        if (days_difference == 1) and (time_difference_hours <= 18):
            return "IN"
        elif (current_date == last_checkin_date): #and (time_difference_hours >= 10)
            return "IN"
        elif days_difference > 1:
            return "IN"
    
    return "IN"