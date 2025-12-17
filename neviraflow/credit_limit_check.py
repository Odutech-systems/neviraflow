import frappe
from frappe import _ 
from frappe.utils import flt, nowdate


class CreditLimitExceedError(frappe.ValidationError):
    pass

def get_customer_outstanding_amount(customer):
    """
    From the GL entry, get the total outstanding amount for the customer.
    The balance will represent the total amount the customer owes the company
    """

    gl_query = frappe.db.sql("""
                    SELECT (SUM(debit) - SUM(credit)) AS outstanding_amount
                    FROM `tabGL Entry`
                    WHERE party_type = 'Customer'
                    AND docstatus = 1
                    AND is_cancelled = 0
                    AND party = %s
                """,(customer),as_dict=True)
    if gl_query:
        return gl_query[0]["outstanding_amount"]
    else:
        return 0
    

def get_customer_credit_limit(customer):
    """
    FRom the credit limits child table, get the customer's credit limit amount
    """
    credit_query = frappe.db.sql("""
                    SELECT  parent, credit_limit 
                    FROM `tabCustomer Credit Limit` WHERE credit_limit > 0
                    AND parent = %s
                    """, (customer), as_dict=True)
    if credit_query:
        return credit_query[0]["credit_limit"]
    else:
        return 0

def get_sales_order_amount(sales_order):
    if sales_order.base_grand_total:
        return flt(sales_order.base_grand_total)
    else:
        return flt(sales_order.total)


def check_customer_credit_status(customer):
    """
    Checks the credit status of the customer and returns a dict with the credit status information
    """
    credit_limit = get_customer_credit_limit(customer)
    outstanding_amount = get_customer_outstanding_amount(customer)

    return {
        "Customer": customer,
        "Credit Limit": credit_limit,
        "Current outstanding": outstanding_amount,
        
    }

