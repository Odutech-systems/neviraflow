# File: neviraflow/procurement/custom_material_request.py

import frappe
import requests
from datetime import datetime
from frappe.utils import nowdate, flt

# -------------------------
# UTILITY: FETCH EXCHANGE RATE (Frankfurter API)
# -------------------------
def fetch_and_set_exchange_rate(from_currency, to_currency, date=None):
    if not date:
        date = nowdate()

    exists = frappe.db.exists("Currency Exchange", {
        "from_currency": from_currency,
        "to_currency": to_currency,
        "date": date
    })
    if exists:
        return

    try:
        url = f"https://api.frankfurter.app/{date}?from={from_currency}&to={to_currency}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            rate = data.get("rates", {}).get(to_currency)
            if rate:
                frappe.get_doc({
                    "doctype": "Currency Exchange",
                    "from_currency": from_currency,
                    "to_currency": to_currency,
                    "exchange_rate": rate,
                    "date": date
                }).insert(ignore_permissions=True)
                frappe.db.commit()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Exchange Rate Fetch Failed")

# -------------------------
# SALES INVOICE: AUTO-ALLOCATE ADVANCES ON LOAD/SAVE
# -------------------------
def before_save_sales_invoice(doc, method):
    if not doc.customer:
        return

    if not doc.items or not any(dn for dn in doc.items if dn.get("delivery_note")):
        frappe.throw("Sales Invoice must be created from a Delivery Note. Direct sales invoicing is not allowed.")

    company_currency = frappe.get_cached_value("Company", doc.company, "default_currency")
    if doc.currency and doc.currency != company_currency:
        fetch_and_set_exchange_rate(doc.currency, company_currency)

    category = frappe.db.get_value("Customer", doc.customer, "customer_category")
    if category == "Cash":
        doc.allocate_advances_automatically = 0
        # Removed automatic allocation logic
        pass

def before_validate_sales_invoice(doc, method):
    return before_save_sales_invoice(doc, method)

# -------------------------
# SALES ORDER: ADVANCE PAYMENT CHECK
# -------------------------
def before_validate_sales_order(doc, method):
    if not doc.customer or not doc.payment_terms_template:
        return

    customer = frappe.get_doc("Customer", doc.customer)
    if customer.get("bypass_advance_payment"):
        return

    if doc.payment_terms_template == "Cash On Delivery":
        _validate_cod_backlog(doc)
    elif doc.payment_terms_template == "Advance Payment":
        _validate_advance_payment(doc)

def before_submit_sales_order(doc, method):
    pass

def _validate_cod_backlog(doc):
    pending_cod = frappe.db.sql("""
        SELECT name FROM `tabSales Order`
        WHERE customer = %s
          AND payment_terms_template = 'Cash On Delivery'
          AND docstatus = 1
          AND status NOT IN ('Draft', 'On Hold','To Deliver and Bill','To Deliver','To Bill')
          AND name != %s
    """, (doc.customer, doc.name), as_dict=True)

    if pending_cod:
        orders = ", ".join(row.name for row in pending_cod)
        frappe.throw(f"Customer has previous Cash On Delivery orders not fully billed or paid: {orders}. Please settle them before submitting a new one.")

def _validate_advance_payment(doc):
    ## Get advance payments from the General Ledger entries
    balance_query = frappe.db.sql("""
                    SELECT
                        (SUM(gl.credit) - SUM(gl.debit)) AS balance_amount 
                        FROM `tabGL Entry` AS gl WHERE gl.docstatus = 1 AND
                        gl.is_cancelled = 0 AND gl.party = %s GROUP BY gl.party 
                    """, (doc.customer), as_dict=True)
    
    ## Initialize the balance amount
    balance_amount = 0
    
    ## Set balance_amount to 0 if no records found
    if not balance_query:
        balance_amount = 0
    else:
        balance_amount = balance_query[0].get("balance_amount")

    tds_threshold = 0.05 ## setting the  tax-witholding threshold

    paid_amount_plus_tds = balance_amount + (balance_amount * tds_threshold)

    if (paid_amount_plus_tds < doc.grand_total) or balance_amount is None:
        frappe.throw(f"Advance Payment Required: Customer has only paid {balance_amount}, but order value is {doc.grand_total}. Please ensure full advance payment before submitting this order.")
# -------------------------
# RFQ, SQ, PO LOGIC
# -------------------------
@frappe.whitelist()
def get_employee_from_user():
    user = frappe.session.user
    employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
    return employee
