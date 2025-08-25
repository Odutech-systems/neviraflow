// Copyright (c) 2025, Victor Mandela and contributors
// For license information, please see license.txt

frappe.ui.form.on('PDC Booking and Clearance', {
  onload(frm) {
    update_ui(frm);
  },

  refresh(frm) {
    update_ui(frm);
  },

  pdc_type(frm) {
    if (frm.doc.pdc_type === 'Customer PDC') {
      frm.set_value('party_type', 'Customer');
    } else if (frm.doc.pdc_type === 'Supplier PDC') {
      frm.set_value('party_type', 'Supplier');
    }
    update_ui(frm);
  },

  party_type(frm) {
    frm.refresh_field('party_code');
  },

  party_code(frm) {
    if (frm.doc.party_type && frm.doc.party_code) {
      const fieldname = frm.doc.party_type === 'Customer' ? 'customer_name' : 'supplier_name';
      frappe.db.get_value(frm.doc.party_type, frm.doc.party_code, fieldname, (r) => {
        if (r) {
          frm.set_value('party_name', r[fieldname]);
        }
      });
    }
  },

  clearance_status(frm) {
    update_ui(frm);
  },

  reference_payment_entry(frm) {
    update_ui(frm);
  }
});

function update_ui(frm) {
  toggle_account_fields(frm);
  toggle_bank_fields(frm);
  lock_clearance_controls(frm);
  toggle_payment_reference_info(frm);
  show_settle_cheque_buttons(frm);
  show_update_clearance_date_button(frm);
}

function toggle_bank_fields(frm) {
  const isCustomer = frm.doc.pdc_type === 'Customer PDC';
  const isSupplier = frm.doc.pdc_type === 'Supplier PDC';

  frm.set_df_property('company_bank_account', 'hidden', !isCustomer);
  frm.set_df_property('party_bank_account', 'hidden', !isSupplier);
}

function toggle_account_fields(frm) {
  const isCustomer = frm.doc.pdc_type === 'Customer PDC';
  const isSupplier = frm.doc.pdc_type === 'Supplier PDC';

  frm.set_df_property('account_paid_to', 'hidden', !isCustomer);
  frm.set_df_property('account_paid_from', 'hidden', !isSupplier);
}

function lock_clearance_controls(frm) {
  const locked = ['Cleared', 'Bounced', 'Cancelled'].includes(frm.doc.clearance_status);
  frm.set_df_property('clearance_status', 'read_only', locked);
  frm.set_df_property('clearance_date', 'read_only', locked);
}

function toggle_payment_reference_info(frm) {
  const show = frm.doc.clearance_status === 'Cleared' && frm.doc.reference_payment_entry;
  frm.set_df_property('reference_payment_entry', 'hidden', !show);
  frm.set_df_property('payment_reference_date', 'hidden', !show);

  if (show) {
    frappe.call({
      method: 'frappe.client.get_value',
      args: {
        doctype: 'Payment Entry',
        filters: { name: frm.doc.reference_payment_entry },
        fieldname: 'posting_date'
      },
      callback(r) {
        if (r.message) {
          frm.set_value('payment_reference_date', r.message.posting_date);
        }
      }
    });
  }
}

function show_settle_cheque_buttons(frm) {
  if (frm.doc.docstatus !== 1 || ['Cleared', 'Bounced', 'Cancelled'].includes(frm.doc.clearance_status)) {
    return;
  }

  frm.add_custom_button(__('Cleared'), () => {
    frappe.call({
      method: 'neviraflow.api.mark_pdc_cleared',
      args: { docname: frm.doc.name },
      callback: () => frm.reload_doc()
    });
  }, __('Settle Cheque'), 'primary');

  frm.add_custom_button(__('Bounced'), () => {
    frappe.prompt([
      {
        fieldname: 'charge_amount',
        label: 'Bounce Charge Amount',
        fieldtype: 'Currency',
        reqd: 1
      },
      {
        fieldname: 'charge_account',
        label: 'Charge Account',
        fieldtype: 'Link',
        options: 'Account',
        reqd: 1,
        default: '4130 - Cheque Bounce Charges - NML'
      }
    ], (values) => {
      frappe.call({
        method: 'neviraflow.api.mark_pdc_bounced',
        args: {
          docname: frm.doc.name,
          charge_amount: values.charge_amount,
          charge_account: values.charge_account
        },
        callback: () => frm.reload_doc()
      });
    }, __('Bounce Details'));
  }, __('Settle Cheque'), 'primary');

  frm.add_custom_button(__('Cancelled'), () => {
    frappe.prompt([
      {
        fieldname: 'cancel_comment',
        label: 'Cancellation Reason',
        fieldtype: 'Small Text',
        reqd: 1
      }
    ], (values) => {
      frappe.call({
        method: 'neviraflow.api.mark_pdc_cancelled',
        args: {
          docname: frm.doc.name,
          comment: values.cancel_comment
        },
        callback: () => frm.reload_doc()
      });
    }, __('Cancel Cheque'));
  }, __('Settle Cheque'), 'primary');
}

function show_update_clearance_date_button(frm) {
  if (frm.doc.docstatus === 1 && frm.doc.clearance_status === "Pending") {
    frm.add_custom_button(__('Update Clearance Date'), () => {
      frappe.prompt([
        {
          fieldname: 'new_date',
          label: 'New Clearance Date',
          fieldtype: 'Date',
          reqd: true,
          default: frm.doc.clearance_date
        }
      ], (values) => {
        frappe.call({
          method: 'neviraflow.api.update_clearance_date',
          args: {
            docname: frm.doc.name,
            new_date: values.new_date
          },
          callback: () => frm.reload_doc()
        });
      }, __('Update Clearance Date'));
    });
  }
}
