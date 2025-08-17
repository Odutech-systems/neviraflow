# Copyright (c) 2025, Victor Mandela
# License: see license.txt

from __future__ import annotations

from typing import Optional
from datetime import datetime, timedelta

import frappe
from frappe.model.document import Document
from frappe.utils import nowdate, nowtime
from frappe import _


# ----------------------------
# Helpers
# ----------------------------

def _to_float(val: Optional[float]) -> float:
    try:
        return float(val) if val is not None else 0.0
    except Exception:
        return 0.0


def _calculate_final_weight(doc: Document) -> None:
    fw = _to_float(doc.first_weight)
    sw = _to_float(doc.second_weight)
    doc.final_weight = max(sw - fw, 0.0)


def _update_weighing_status(doc: Document) -> None:
    fw = _to_float(doc.first_weight)
    sw = _to_float(doc.second_weight)
    if fw <= 0:
        doc.weighing_status = "Pending First Weight"
    elif fw > 0 and sw <= 0:
        doc.weighing_status = "Awaiting Second Weight"
    elif sw > fw:
        # Both weights present and valid; business rules move to capture step
        doc.weighing_status = "Ready for Capture"


def _sync_gross_tare_net(doc: Document) -> None:
    # Map new display fields to core fields if they exist in the schema
    if hasattr(doc, "gross_weight"):
        doc.gross_weight = doc.second_weight or 0
    if hasattr(doc, "tare_weight"):
        doc.tare_weight = doc.first_weight or 0
    if hasattr(doc, "nett_weight"):
        doc.nett_weight = doc.final_weight or 0
    # Ticket number mirrors the document ID/name
    if hasattr(doc, "ticket_number") and doc.name:
        doc.ticket_number = doc.name


def _set_multi_weighing_flags(doc: Document) -> None:
    """Maintain multi-weighing flags if present on the DocType.
    - current_weighing_no defaults to 1
    - If has_multiple_weights and totals are set, set is_final_weighing accordingly
    """
    if hasattr(doc, "current_weighing_no") and not doc.current_weighing_no:
        doc.current_weighing_no = 1

    if getattr(doc, "has_multiple_weights", 0):
        total = getattr(doc, "total_weighings_expected", None)
        if total and doc.current_weighing_no:
            doc.is_final_weighing = 1 if int(doc.current_weighing_no) >= int(total) else 0
    else:
        # Single weighing implies final
        if hasattr(doc, "is_final_weighing"):
            doc.is_final_weighing = 1


def _ensure_total_when_multiple(doc: Document) -> None:
    if getattr(doc, "has_multiple_weights", 0) and not getattr(doc, "total_weighings_expected", None):
        frappe.throw(_("Please set Total Weighings Expected when 'Has Multiple Weights' is checked."))


def _prevent_changes_after_capture(doc: Document) -> None:
    """Server-side lock: once capture completed (status Completed) or outbound linked,
    prevent tampering with item_type/weights. Presence of child rows alone should NOT lock.
    """
    before = getattr(doc, "_doc_before_save", None)
    if not before:
        try:
            before = doc.get_doc_before_save()  # type: ignore[attr-defined]
        except Exception:
            before = None

    captured = doc.weighing_status == "Completed" or bool(getattr(doc, "stock_entry_reference", None))
    if captured and before:
        for f in ["item_type", "first_weight", "second_weight"]:
            if before.get(f) != doc.get(f):
                frappe.throw(_("{0} cannot be changed after capture.").format(f.replace("_", " ").title()))


# ----------------------------
# DocType Controller
# ----------------------------
class WeighbridgeManagement(Document):
    def validate(self):
        _update_weighing_status(self)
        if self.first_weight and self.second_weight:
            _calculate_final_weight(self)
        _sync_gross_tare_net(self)
        _set_multi_weighing_flags(self)
        if getattr(self, "has_multiple_weights", 0):
            _ensure_total_when_multiple(self)
        _prevent_changes_after_capture(self)

    def before_submit(self):
        # Re-sync just before submit
        if self.first_weight and self.second_weight:
            _calculate_final_weight(self)
        _sync_gross_tare_net(self)
        _set_multi_weighing_flags(self)


# ----------------------------
# Capture Methods
# ----------------------------
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
    if sw <= fw:
        frappe.throw(_("Second weight must be greater than first weight."))

    final_weight = sw - fw

    weight_per_unit = frappe.db.get_value("Item", item_code, "weight_per_unit") or 0
    item_name = frappe.db.get_value("Item", item_code, "item_name")
    item_uom = frappe.db.get_value("Item", item_code, "stock_uom")

    doc.item_type = "Raw Materials"
    doc.second_weight = sw
    doc.final_weight = final_weight
    doc.quarry_from = quarry_from
    doc.set("item_details", [])

    row = doc.append("item_details", {})
    row.item_code = item_code
    row.item_description = item_name
    row.uom = item_uom
    row.quantity = (final_weight / (weight_per_unit * 1000)) if weight_per_unit else (final_weight / 1000)

    doc.weighing_status = "Completed"
    doc.save(ignore_permissions=True)
    return "Return weight and item details captured successfully."


@frappe.whitelist()
def confirm_rm_receipt(docname: str):
    doc = frappe.get_doc("Weighbridge Management", docname)

    if doc.docstatus != 1:
        frappe.throw(_("Only submitted documents can be confirmed."))
    if doc.weighing_status != "Completed":
        frappe.throw(_("Weighing must be completed before confirmation."))
    if not getattr(doc, "item_details", None):
        frappe.throw(_("Item details must be filled before confirmation."))

    stock_entry = frappe.new_doc("Stock Entry")
    stock_entry.stock_entry_type = "Material Receipt"
    stock_entry.posting_date = nowdate()
    stock_entry.posting_time = nowtime()

    for row in doc.item_details:
      
        default_warehouse = frappe.db.get_value(
            "Item Default", {"parent": row.item_code}, "default_warehouse"
        )
        if not default_warehouse:
            frappe.throw(_("Item {0} does not have a default warehouse set.").format(row.item_code))

        stock_entry.append(
            "items",
            {
                "item_code": row.item_code,
                "qty": row.quantity,
                "uom": row.uom or frappe.db.get_value("Item", row.item_code, "stock_uom"),
                "conversion_factor": 1,
                "t_warehouse": default_warehouse,
            },
        )

    stock_entry.insert(ignore_permissions=True)
    stock_entry.submit()

    doc.db_set("stock_entry_reference", stock_entry.name)
    return stock_entry.name


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
    final_weight = sw - fw
    if final_weight <= 0:
        frappe.throw(_("Second weight must be greater than first weight."))

    weight_per_unit = frappe.db.get_value("Item", item_code, "weight_per_unit") or 0
    item_uom = frappe.db.get_value("Item", item_code, "stock_uom") or "Tonne"

    doc.item_type = item_type
    doc.second_weight = sw
    doc.final_weight = final_weight
    doc.weighing_status = "Completed"

    doc.set("item_details", [])
    item_row = doc.append("item_details", {})
    item_row.item_code = item_code
    item_row.uom = item_uom
    item_row.quantity = (final_weight / (weight_per_unit * 1000)) if weight_per_unit else (final_weight / 1000)

    doc.save(ignore_permissions=True)
    return "Captured"


@frappe.whitelist()
def confirm_production_transfer(docname: str, work_order: str):
    doc = frappe.get_doc("Weighbridge Management", docname)

    if doc.docstatus != 1 or doc.item_type != "Raw Materials - Production":
        frappe.throw(_("Only submitted Raw Materials - Production documents can be processed."))

    if not doc.final_weight or not getattr(doc, "item_details", None):
        frappe.throw(_("Final weight or item details missing."))
    if not work_order:
        frappe.throw(_("Work Order is required."))

    doc.work_order = work_order
    stock_entry = frappe.new_doc("Stock Entry")
    stock_entry.stock_entry_type = "Material Transfer for Manufacture"
    stock_entry.posting_date = nowdate()
    stock_entry.posting_time = nowtime()
    stock_entry.work_order = work_order

    for item in doc.item_details:
        default_warehouse = frappe.db.get_value(
            "Item Default", {"parent": item.item_code}, "default_warehouse"
        )
        if not default_warehouse:
            frappe.throw(_("Default warehouse missing for item {0}.").format(item.item_code))

        item_uom = frappe.db.get_value("Item", item.item_code, "stock_uom") or "Kg"

        stock_entry.append(
            "items",
            {
                "item_code": item.item_code,
                "qty": item.quantity,
                "uom": item_uom,
                "conversion_factor": 1,
                "s_warehouse": default_warehouse,
                "t_warehouse": "Production WIP - NML",
            },
        )

    stock_entry.insert(ignore_permissions=True)
    stock_entry.submit()

    doc.db_set("stock_entry_reference", stock_entry.name)
    return stock_entry.name


@frappe.whitelist()
def capture_partner_production(docname: str, partner_items: str):
    doc = frappe.get_doc("Weighbridge Management", docname)

    items = frappe.parse_json(partner_items)
    if not items:
        frappe.throw(_("No partner items provided."))

    if doc.weighing_status == "Completed":
        frappe.throw(_("This ticket has already been captured."))

    doc.item_type = "Partner Production"
    doc.set("partner_item_list", [])

    for item in items:
        row = doc.append("partner_item_list", {})
        row.partner_description = item.get("partner_description")
        row.item_description = item.get("item_description")
        row.first_weight = item.get("first_weight")
        row.second_weight = item.get("second_weight")
        row.quantity = item.get("quantity")

    if items:
        first = _to_float(items[0].get("first_weight"))
        second = _to_float(items[0].get("second_weight"))
        final = second - first
        if final > 0:
            doc.second_weight = second
            doc.final_weight = final
            doc.weighing_status = "Completed"

    doc.save(ignore_permissions=True)
    return "Success"


@frappe.whitelist()
def capture_customer_transfer(
    docname: str,
    second_weight: float,
    item_code: Optional[str] = None,
    customer_name: Optional[str] = None,
    item_type: Optional[str] = None,
):
    doc = frappe.get_doc("Weighbridge Management", docname)

    doc.item_type = item_type or doc.item_type

    if doc.docstatus != 1:
        frappe.throw(_("Only submitted documents can be updated."))
    if not doc.first_weight:
        frappe.throw(_("First weight must be recorded."))

    if doc.weighing_status == "Completed":
        frappe.throw(_("This ticket has already been captured."))

    sw = _to_float(second_weight)
    fw = _to_float(doc.first_weight)
    if sw <= fw:
        frappe.throw(_("Second weight must be greater than first weight."))

    final_weight = sw - fw
    tonnage = final_weight / 1000

    # TODO: replace description parsing with explicit pack size on Item
    packaging_weight = 50
    if item_code:
        item_pack = frappe.db.get_value("Item", item_code, "description") or ""
        text = (item_pack or "").lower()
        if "25" in text:
            packaging_weight = 25
        elif "1" in text and "tonne" in text:
            packaging_weight = 1000

    bags = int(final_weight // packaging_weight)

    doc.second_weight = sw
    doc.final_weight = final_weight
    doc.weighing_status = "Completed"

    doc.set("customer_item_description", [])
    row = doc.append("customer_item_description", {})
    row.customer_name = customer_name
    row.item_description = item_code  # stores code; UI shows name in dialog
    row.tonnage = tonnage
    row.bags = bags
    row.sales_order = None
    row.weighing_batch = None

    doc.save(ignore_permissions=True)
    return "Finished Goods transfer captured."


@frappe.whitelist()
def capture_inter_company_transfer(
    docname: str,
    second_weight: float,
    item_code: Optional[str] = None,
    item_type: Optional[str] = None,
):
    doc = frappe.get_doc("Weighbridge Management", docname)

    doc.item_type = item_type or doc.item_type

    if doc.docstatus != 1:
        frappe.throw(_("Only submitted documents can be updated."))
    if not doc.first_weight:
        frappe.throw(_("First weight must be recorded."))

    if doc.weighing_status == "Completed":
        frappe.throw(_("This ticket has already been captured."))

    sw = _to_float(second_weight)
    fw = _to_float(doc.first_weight)
    if sw <= fw:
        frappe.throw(_("Second weight must be greater than first weight."))

    final_weight = sw - fw
    tonnage = final_weight / 1000

    # TODO: replace description parsing with explicit pack size on Item
    packaging_weight = 50
    if item_code:
        item_pack = frappe.db.get_value("Item", item_code, "description") or ""
        text = (item_pack or "").lower()
        if "25" in text:
            packaging_weight = 25
        elif "1" in text and "tonne" in text:
            packaging_weight = 1000

    bags = int(final_weight // packaging_weight)

    doc.second_weight = sw
    doc.final_weight = final_weight
    doc.weighing_status = "Completed"

    doc.set("company_transfer", [])
    row = doc.append("company_transfer", {})
    row.item_code = item_code
    row.tonnage = tonnage
    row.bag = bags
    row.weighing_batch = None

    doc.save(ignore_permissions=True)
    return "Inter-Company Transfer captured."


# ----------------------------
# Auto-submit fallback for /api/resource inserts
# ----------------------------
@frappe.whitelist()  # not strictly needed for doc_events
def auto_submit_if_ready(doc: Document, method: Optional[str] = None):
    """Auto-submit when both weights are present and valid. Sets status to Ready for Capture."""
    try:
        fw = _to_float(doc.first_weight)
        sw = _to_float(doc.second_weight)
        if doc.docstatus == 0 and fw > 0 and sw > fw:
            if not doc.final_weight:
                doc.final_weight = sw - fw
            doc.weighing_status = "Ready for Capture"
            _sync_gross_tare_net(doc)
            _set_multi_weighing_flags(doc)
            doc.flags.ignore_permissions = True
            doc.submit()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "WM Auto Submit Failed")


