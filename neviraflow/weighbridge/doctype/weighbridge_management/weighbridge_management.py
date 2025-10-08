# Copyright (c) 2025, Victor Mandela
# License: see license.txt

from __future__ import annotations

from typing import Optional
import json

import frappe
from frappe.model.document import Document
from frappe.utils import nowdate, nowtime
from frappe import _

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _to_float(val: Optional[float]) -> float:
    try:
        return float(val) if val is not None else 0.0
    except Exception:
        return 0.0


def _calculate_final_weight(doc: Document) -> None:
    fw = _to_float(doc.first_weight)
    sw = _to_float(doc.second_weight)
    doc.final_weight = abs(sw - fw)


def _update_weighing_status(doc: Document) -> None:
    """Frontline status logic during edit/submit (NOT during capture).
    - When both weights are present, we move to Ready for Capture for ALL types.
    - Pending Confirmation is set ONLY by capture methods for RM / RM Production.
    """
    fw = _to_float(doc.first_weight)
    sw = _to_float(doc.second_weight)

    if fw <= 0:
        doc.weighing_status = "Pending First Weight"
    elif fw > 0 and sw <= 0:
        doc.weighing_status = "Awaiting Second Weight"
    elif sw > 0:
        doc.weighing_status = "Ready for Capture"


def _sync_gross_tare_net(doc: Document) -> None:
    # Map display -> core, if fields exist
    if hasattr(doc, "gross_weight"):
        doc.gross_weight = doc.second_weight or 0
    if hasattr(doc, "tare_weight"):
        doc.tare_weight = doc.first_weight or 0
    if hasattr(doc, "net_weight"):
        doc.net_weight = doc.final_weight or 0
    if hasattr(doc, "ticket_number") and doc.name:
        doc.ticket_number = doc.name


def _set_multi_weighing_flags(doc: Document) -> None:
    if hasattr(doc, "current_weighing_no") and not doc.current_weighing_no:
        doc.current_weighing_no = 1

    if getattr(doc, "has_multiple_weights", 0):
        total = getattr(doc, "total_weighings_expected", None)
        if total and doc.current_weighing_no:
            doc.is_final_weighing = 1 if int(doc.current_weighing_no) >= int(total) else 0
    else:
        if hasattr(doc, "is_final_weighing"):
            doc.is_final_weighing = 1


def _ensure_total_when_multiple(doc: Document) -> None:
    if getattr(doc, "has_multiple_weights", 0) and not getattr(doc, "total_weighings_expected", None):
        frappe.throw(_("Please set Total Weighings Expected when 'Has Multiple Weights' is checked."))


def _prevent_changes_after_capture(doc: Document) -> None:
    """Server-side lock: once capture is completed or stock entry exists, block changes."""
    before = getattr(doc, "_doc_before_save", None)
    if not before:
        try:
            before = doc.get_doc_before_save()
        except Exception:
            before = None

    captured = doc.weighing_status == "Completed" or bool(getattr(doc, "stock_entry_reference", None))
    if captured and before:
        for f in ["item_type", "first_weight", "second_weight"]:
            if before.get(f) != doc.get(f):
                frappe.throw(_("{0} cannot be changed after capture.").format(f.replace("_", " ").title()))


def _kgs_to_tonnes(kg: float) -> float:
    return round(_to_float(kg) / 1000.0, 6)


def _detect_packaging_weight(item_code: str) -> float:
    """Try to guess bag size from Item description. Defaults to 50Kg if unknown.
    NOTE: Replace this with an explicit custom field on Item if available.
    """
    desc = (frappe.db.get_value("Item", item_code, "description") or "").lower()
    # Priority: 1 tonne, then 25kg, else 50kg default
    if "1" in desc and "tonne" in desc:
        return 1000.0
    if "25" in desc:
        return 25.0
    return 50.0

def _assign_item_link_fields(row, item_code: str):
    """Force item CODE into any likely item link fields on child rows."""
    for fname in ("item_code", "item", "item_name", "item_description"):
        if hasattr(row, fname):
            setattr(row, fname, item_code)

def _assign_customer_link_fields(row, customer_code: str):
    """Force customer CODE into any likely customer link fields on child rows."""
    for fname in ("customer", "customer_name"):
        if hasattr(row, fname):
            setattr(row, fname, customer_code)

def _safe_get_value(doctype: str, name: str, field: str):
    """Return value if field exists on the doctype, else None (avoids SQL errors)."""
    try:
        meta = frappe.get_meta(doctype)
        if meta and meta.has_field(field):
            return frappe.db.get_value(doctype, name, field)
    except Exception:
        pass
    return None

def _get_pack_and_tare(item_code: str) -> tuple[float, float]:
    """
    Returns (pack_size_kg, bag_tare_kg) without assuming custom fields exist.
    Falls back to parsing Item.description:
      - contains '1' and 'tonne'  -> 1000 kg
      - contains '25'             -> 25 kg
      - default                   -> 50 kg
    Default tare = 0.2 kg if not found.
    """
    # Try custom fields only if they exist
    pack = _safe_get_value("Item", item_code, "pack_size_kg")
    tare = _safe_get_value("Item", item_code, "bag_tare_kg")

    pack_kg = float(pack) if pack not in (None, "") else 0.0
    tare_kg = float(tare) if tare not in (None, "") else 0.0

    if not pack_kg:
        desc = (frappe.db.get_value("Item", item_code, "description") or "").lower()
        if "1" in desc and "tonne" in desc:
            pack_kg = 1000.0
        elif "25" in desc:
            pack_kg = 25.0
        else:
            pack_kg = 50.0

    if not tare_kg:
        # sensible fallback if no custom field
        tare_kg = 0.2

    return pack_kg, tare_kg




# -------------------------------------------------------------------
# DocType Controller
# -------------------------------------------------------------------
class WeighbridgeManagement(Document):
    def validate(self):
        if self.first_weight and self.second_weight:
            _calculate_final_weight(self)
        _update_weighing_status(self)
        _sync_gross_tare_net(self)
        _set_multi_weighing_flags(self)
        if getattr(self, "has_multiple_weights", 0):
            _ensure_total_when_multiple(self)
        _prevent_changes_after_capture(self)

    def before_submit(self):
        if self.first_weight and self.second_weight:
            _calculate_final_weight(self)
        _sync_gross_tare_net(self)
        _set_multi_weighing_flags(self)
        _update_weighing_status(self)


# -------------------------------------------------------------------
# Capture Methods (set child tables + advance status)
# -------------------------------------------------------------------
@frappe.whitelist()
def capture_raw_material_return(docname: str, second_weight: float, item_code: str, quarry_from: str):
    doc = frappe.get_doc("Weighbridge Management", docname)

    if doc.docstatus != 1:
        frappe.throw(_("Only submitted documents can be updated."))
    if not doc.first_weight:
        frappe.throw(_("First weight must be recorded before capturing return."))
    if doc.weighing_status == "Completed":
        frappe.throw(_("This ticket has already been captured."))

    sw = _to_float(second_weight)
    fw = _to_float(doc.first_weight)
    final_weight = abs(sw - fw)

    item_name = frappe.db.get_value("Item", item_code, "item_name")
    item_uom = frappe.db.get_value("Item", item_code, "stock_uom") or "Kg"
    weight_per_unit = _to_float(frappe.db.get_value("Item", item_code, "weight_per_unit") or 0)

    # Update doc core
    doc.item_type = "Raw Materials"
    doc.second_weight = sw
    doc.final_weight = final_weight
    doc.quarry_from = quarry_from

    # Child table
    doc.set("item_details", [])
    row = doc.append("item_details", {})
    row.item_code = item_code
    row.item_description = item_name
    row.uom = item_uom
    # Convert to TONNES; use weight_per_unit if present (units per tonne)
    row.quantity = (final_weight / (weight_per_unit * 1000)) if weight_per_unit else _kgs_to_tonnes(final_weight)

    # RM goes to pending confirmation
    doc.weighing_status = "Pending Confirmation"
    doc.save(ignore_permissions=True)
    return "Raw material captured."


@frappe.whitelist()
def capture_production_material_return(docname: str, second_weight: float, item_code: str, item_type: str):
    doc = frappe.get_doc("Weighbridge Management", docname)

    if doc.docstatus != 1:
        frappe.throw(_("Only submitted documents can be updated."))
    if not doc.first_weight:
        frappe.throw(_("First weight must be recorded first."))
    if doc.weighing_status == "Completed":
        frappe.throw(_("This ticket has already been captured."))

    sw = _to_float(second_weight)
    fw = _to_float(doc.first_weight)
    final_weight = abs(sw - fw)

    item_name = frappe.db.get_value("Item", item_code, "item_name")
    item_uom = frappe.db.get_value("Item", item_code, "stock_uom") or "Kg"
    weight_per_unit = _to_float(frappe.db.get_value("Item", item_code, "weight_per_unit") or 0)

    doc.item_type = item_type  # expected: "Raw Materials - Production"
    doc.second_weight = sw
    doc.final_weight = final_weight

    doc.set("item_details", [])
    r = doc.append("item_details", {})
    r.item_code = item_code
    r.item_description = item_name
    r.uom = item_uom
    r.quantity = (final_weight / (weight_per_unit * 1000)) if weight_per_unit else _kgs_to_tonnes(final_weight)

    # RM Production also requires confirmation (transfer for manufacture)
    doc.weighing_status = "Pending Confirmation"
    doc.save(ignore_permissions=True)
    return "Production material captured."


@frappe.whitelist()
def capture_purchased_material(docname: str, second_weight: float, item_code: str):
    """For Purchased Materials we do NOT convert; store net weight (Kg) directly.
    Quantity is the final weight in KG; receipt happens via Purchase Receipt separately.
    """
    doc = frappe.get_doc("Weighbridge Management", docname)

    if doc.docstatus != 1:
        frappe.throw(_("Only submitted documents can be updated."))
    if doc.weighing_status == "Completed":
        frappe.throw(_("This ticket has already been captured."))

    sw = _to_float(second_weight)
    fw = _to_float(doc.first_weight)
    final_weight = abs(sw - fw)

    item_name = frappe.db.get_value("Item", item_code, "item_name")
    item_uom = frappe.db.get_value("Item", item_code, "stock_uom") or "Kg"

    doc.item_type = "Purchased Materials"
    doc.second_weight = sw
    doc.final_weight = final_weight

    doc.set("purchased_item_list", [])
    r = doc.append("purchased_item_list", {})
    r.item_code = item_code
    r.item_name = item_name
    r.uom = item_uom
    r.quantity = final_weight  # as requested: keep KG, no conversion

    # Purchased completes at capture
    doc.weighing_status = "Completed"
    doc.save(ignore_permissions=True)
    return "Purchased material captured."


@frappe.whitelist()
def capture_inter_company_transfer(docname: str, second_weight: float, item_code: str):
    doc = frappe.get_doc("Weighbridge Management", docname)

    if doc.docstatus != 1:
        frappe.throw(_("Only submitted documents can be updated."))
    if doc.weighing_status == "Completed":
        frappe.throw(_("This ticket has already been captured."))

    sw = _to_float(second_weight)
    fw = _to_float(doc.first_weight)
    final_weight = abs(sw - fw)

    item_uom = frappe.db.get_value("Item", item_code, "stock_uom") or "Kg"
    pack_kg, tare_kg = _get_pack_and_tare(item_code)

    bags = int(final_weight // (pack_kg + tare_kg)) if (pack_kg + tare_kg) > 0 else 0
    net_product_kg = max(final_weight - bags * tare_kg, 0)
    tonnage = round(net_product_kg / 1000.0, 6)

    doc.item_type = "Inter-Company Transfer"
    doc.second_weight = sw
    doc.final_weight = final_weight

    doc.set("company_transfer", [])
    r = doc.append("company_transfer", {})

    _assign_item_link_fields(r, item_code)
    if hasattr(r, "uom"):
        r.uom = item_uom

    if hasattr(r, "tonnage"):
        r.tonnage = tonnage
    if hasattr(r, "quantity"):
        r.quantity = tonnage

    if hasattr(r, "bags"):
        r.bags = bags
    if hasattr(r, "bag"):
        r.bag = bags

    doc.weighing_status = "Completed"
    doc.save(ignore_permissions=True)
    return "Inter-Company Transfer captured."



@frappe.whitelist()
def capture_finished_goods(docname: str, second_weight: float, item_code: str, customer: str):
    doc = frappe.get_doc("Weighbridge Management", docname)

    if doc.docstatus != 1:
        frappe.throw(_("Only submitted documents can be updated."))
    if doc.weighing_status == "Completed":
        frappe.throw(_("This ticket has already been captured."))

    sw = _to_float(second_weight)
    fw = _to_float(doc.first_weight)
    final_weight = abs(sw - fw)  # total weighed kg (product + bag tare)

    # Use codes for links; do NOT write human names into link fields
    item_uom = frappe.db.get_value("Item", item_code, "stock_uom") or "Kg"
    pack_kg, tare_kg = _get_pack_and_tare(item_code)

    # Estimate bags as floor(weight / (pack + tare))
    bags = int(final_weight // (pack_kg + tare_kg)) if (pack_kg + tare_kg) > 0 else 0
    # Net product kg excluding tare
    net_product_kg = max(final_weight - bags * tare_kg, 0)
    tonnage = round(net_product_kg / 1000.0, 6)

    doc.item_type = "Finished Goods"
    doc.second_weight = sw
    doc.final_weight = final_weight

    doc.set("customer_item_description", [])
    r = doc.append("customer_item_description", {})

    # Write codes to any likely Link fields
    _assign_item_link_fields(r, item_code)
    _assign_customer_link_fields(r, customer)

    if hasattr(r, "uom"):
        r.uom = item_uom

    # Tonnage / Quantity
    if hasattr(r, "tonnage"):
        r.tonnage = tonnage
    if hasattr(r, "quantity"):
        r.quantity = tonnage  # if your grid uses quantity for tonnes

    # Bags
    if hasattr(r, "bags"):
        r.bags = bags
    if hasattr(r, "bag"):
        r.bag = bags

    doc.weighing_status = "Completed"
    doc.save(ignore_permissions=True)
    return "Finished Goods captured."




@frappe.whitelist()
def capture_partner_production(docname: str, partner_items: str):
    """Capture rows into partner_item_list.
    partner_items is a JSON array of objects:
    [{ partner_description, item_description, first_weight, second_weight, quantity }]
    If quantity missing, default from final_weight (in tonnes).
    """
    doc = frappe.get_doc("Weighbridge Management", docname)

    if doc.docstatus != 1:
        frappe.throw(_("Only submitted documents can be updated."))
    if doc.weighing_status == "Completed":
        frappe.throw(_("This ticket has already been captured."))

    try:
        items = frappe.parse_json(partner_items)
    except Exception:
        items = []

    sw = _to_float(doc.second_weight)
    fw = _to_float(doc.first_weight)
    final_weight = abs(sw - fw)

    doc.item_type = "Partner Production"
    doc.set("partner_item_list", [])

    if items:
        for it in items:
            r = doc.append("partner_item_list", {})
            r.partner_description = it.get("partner_description")
            r.item_description = it.get("item_description")
            r.first_weight = it.get("first_weight")
            r.second_weight = it.get("second_weight")
            r.quantity = it.get("quantity") or _kgs_to_tonnes(final_weight)
    else:
        # Fallback single row from final weight
        r = doc.append("partner_item_list", {})
        r.partner_description = "Auto"
        r.item_description = "Auto"
        r.quantity = _kgs_to_tonnes(final_weight)

    # Partner Production completes at capture
    doc.weighing_status = "Completed"
    doc.save(ignore_permissions=True)
    return "Partner Production captured."


# -------------------------------------------------------------------
# Confirmation Methods (create Stock Entry)
# -------------------------------------------------------------------
@frappe.whitelist()
def confirm_rm_receipt(docname: str):
    doc = frappe.get_doc("Weighbridge Management", docname)

    if doc.docstatus != 1:
        frappe.throw(_("Only submitted documents can be confirmed."))
    if doc.weighing_status != "Pending Confirmation":
        frappe.throw(_("Weighing must be in 'Pending Confirmation' status."))
    if not getattr(doc, "item_details", None):
        frappe.throw(_("Item details must be filled before confirmation."))
    if doc.stock_entry_reference:
        frappe.throw(_("Stock Entry already created for this record."))

    se = frappe.new_doc("Stock Entry")
    se.stock_entry_type = "Material Receipt"
    se.posting_date = nowdate()
    se.posting_time = nowtime()

    for row in doc.item_details:
        default_wh = frappe.db.get_value("Item Default", {"parent": row.item_code}, "default_warehouse")
        if not default_wh:
            frappe.throw(_("Item {0} does not have a default warehouse set.").format(row.item_code))

        se.append("items", {
            "item_code": row.item_code,
            "qty": row.quantity,
	    "expense_account":"1420 - Mining WIP - NML",
            "uom": row.uom or frappe.db.get_value("Item", row.item_code, "stock_uom"),
            "conversion_factor": 1,
            "t_warehouse": default_wh,
        })

    se.insert(ignore_permissions=True)
    se.submit()

    doc.db_set("stock_entry_reference", se.name)
    doc.db_set("weighing_status", "Completed")
    return se.name


@frappe.whitelist()
def confirm_production_transfer(docname: str, work_order: str):
    doc = frappe.get_doc("Weighbridge Management", docname)

    if doc.docstatus != 1 or doc.item_type != "Raw Materials - Production":
        frappe.throw(_("Only submitted Raw Materials - Production documents can be processed."))
    if not doc.final_weight or not getattr(doc, "item_details", None):
        frappe.throw(_("Final weight or item details missing."))
    if not work_order:
        frappe.throw(_("Work Order is required."))
    if doc.stock_entry_reference:
        frappe.throw(_("Stock Entry already created for this record."))

    doc.work_order = work_order

    se = frappe.new_doc("Stock Entry")
    se.stock_entry_type = "Material Transfer for Manufacture"
    se.posting_date = nowdate()
    se.posting_time = nowtime()
    se.work_order = work_order

    for row in doc.item_details:
        default_wh = frappe.db.get_value("Item Default", {"parent": row.item_code}, "default_warehouse")
        if not default_wh:
            frappe.throw(_("Default warehouse missing for item {0}.".format(row.item_code)))

        uom = row.uom or frappe.db.get_value("Item", row.item_code, "stock_uom") or "Kg"
        se.append("items", {
            "item_code": row.item_code,
            "qty": row.quantity,
            "uom": uom,
            "conversion_factor": 1,
            "s_warehouse": default_wh,
            "t_warehouse": "Production WIP - NML",
        })

    se.insert(ignore_permissions=True)
    se.submit()

    doc.db_set("stock_entry_reference", se.name)
    doc.db_set("weighing_status", "Completed")
    return se.name


# -------------------------------------------------------------------
# Auto-submit fallback for API inserts
# -------------------------------------------------------------------
@frappe.whitelist()
def auto_submit_if_ready(doc: Document, method: Optional[str] = None):
    """
    Hybrid auto-submit:
    - Works when doc is created via REST API (e.g., via .insert())
    - Skips auto-submit when used via UI or when already submitted
    """
    try:
        # Don't proceed if already submitted
        if doc.docstatus != 0:
            return

        fw = _to_float(doc.first_weight)
        sw = _to_float(doc.second_weight)

        # Both weights must be present and greater than 0
        if fw > 0 and sw > 0:
            # Prevent re-submission if already exists
            if not doc.final_weight:
                doc.final_weight = abs(sw - fw)

            doc.weighing_status = "Ready for Capture"
            _sync_gross_tare_net(doc)
            _set_multi_weighing_flags(doc)

            # Avoid errors on manual UI save
            doc.flags.ignore_permissions = True

            # Ensure we don't submit again if already exists
            if not frappe.db.exists("Weighbridge Management", doc.name):
                frappe.log_error(f"{doc.name} does not exist in DB; skipping submit.", "Hybrid Auto Submit")
                return

            # Double-check status before submission
            existing = frappe.get_doc("Weighbridge Management", doc.name)
            if existing.docstatus == 0:
                doc.submit()
                frappe.log_error(f"{doc.name} auto-submitted successfully.", "Hybrid Auto Submit")
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Hybrid Auto Submit Failed")
