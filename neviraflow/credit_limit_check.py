import frappe
from frappe import _ 
from frappe.utils import flt, nowdate


class CreditLimitExceedError(frappe.ValidationError):
    pass


def validate_credit_limit(doc, method=None):
    if not doc.customer:
        return
    
    customer_credit_limit = get_customer_credit_limit(doc.customer)
    
    if not customer_credit_limit or 0:
        return
    total_outstanding = get_customer_outstanding_amount(doc.customer)

    current_order_amount = get_sales_order_amount(doc)

    ## Get the projected total after order is created
    projected_total = total_outstanding + current_order_amount

    ## Current available credit
    current_available_credit = customer_credit_limit - total_outstanding
    
    credit_utilization_percentage = (total_outstanding / customer_credit_limit * 100) if customer_credit_limit > 0 else 0

    if projected_total > customer_credit_limit:
        frappe.throw(
            _("Credit limit Exceeded for customer : {0}<br>br>"
              "Credit Summary: </br></br>"
              "Credit Limit: {1} </br>"
              "Current Outstanding amount: {2} ({3}% Utilised) </br>"
              "This order amount : {4} </br>"
              "Projected Total: {5} </br>"
              "Available credit: {6} </br></br>"
              "Credit exceeded by: {7} </br>"
              "Possible Solutions: <br>"
              "1. Request credit limit increase or reduce the order amount"
            ).format(
                frappe.bold(doc.customer_name),
                frappe.utils.fmt_money(customer_credit_limit),
                frappe.utils.fmt_money(total_outstanding),
                round(credit_utilization_percentage,2),
                frappe.utils.fmt_money(current_order_amount),
                frappe.utils.fmt_money(projected_total),
                frappe.utils.fmt_money(current_available_credit),
                frappe.utils.fmt_monet(projected_total - customer_credit_limit)
            ), title=_("Credit Limit Exceeded"), 
            exc=CreditLimitExceedError,
        )
        
    elif credit_utilization_percentage >= 60:
        frappe.msgprint(
            _("High Credit Utilization for {0} </br>"
              "Credit Limit: {1} </br>"
              "Current Utilization: {2}% <br>"
            ).format(
                  doc.customer_name,
                  frappe.utils.fmt_money(customer_credit_limit),
                  round(credit_utilization_percentage,2)
            ),
            title=_("High credit Utilization warning"),
            indicator = "yellow"
        )



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
        "customer": customer,
        "credit_limit": credit_limit,
        "current_outstanding": outstanding_amount,
        "credit_utilization_percentage": ((outstanding_amount / credit_limit) * 100) if credit_limit > 0 else 0
    }

