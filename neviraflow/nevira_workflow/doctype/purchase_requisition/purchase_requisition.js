// Copyright (c) 2025, Victor Mandela and contributors
// For license information, please see license.txt

frappe.ui.form.on('Purchase Requisition', {
  onload: function(frm) {
    if (frm.doc.__islocal && frm.doc.requester_type === "Self") {
      frappe.call({
        method: "frappe.client.get_list",
        args: {
          doctype: "Employee",
          filters: { user_id: frappe.session.user },
          fields: ["name"]
        },
        callback: function(r) {
          if (r.message && r.message.length > 0) {
            frm.set_value("requester_id", r.message[0].name);
          }
        }
      });
    }
  }
});
