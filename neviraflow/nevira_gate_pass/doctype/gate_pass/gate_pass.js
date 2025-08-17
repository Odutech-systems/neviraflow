// Copyright (c) 2025, Victor Mandela and contributors
// For license information, please see license.txt

frappe.ui.form.on('Gate Pass', {
    onload: function(frm) {
        if (!frm.doc.dispatch_representative) {
            frm.set_value('dispatch_representative', frappe.session.user);
        }
    },

    gate_pass_type: function(frm) {
        if (frm.doc.gate_pass_type === "Outgoing") {
            frm.set_value('gate_pass_status', 'Check and Dispatch');
        } else if (frm.doc.gate_pass_type === "Incoming") {
            frm.set_value('gate_pass_status', 'Check and Receive');
        }
    },

    customer_name: function(frm) {
        frm.set_query("customer_delivery_note", function () {
            return {
                query: "neviraflow.nevira_gate_pass.doctype.gate_pass.gate_pass.get_available_delivery_notes",
                filters: {
                    customer: frm.doc.customer_name
                }
            };
        });
    }
});
