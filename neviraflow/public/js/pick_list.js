frappe.ui.form.on("Pick List", {
  onload(frm) {
    apply_bag_tonne_logic("Pick List Item");

    if (frm.doc.parent_warehouse) {
      frm.doc.locations.forEach(row => {
        if (!row.warehouse) {
          frappe.model.set_value(row.doctype, row.name, "warehouse", frm.doc.parent_warehouse);
        }
      });
    }

    frm.fields_dict.locations.grid.on("add_row", function (grid_row) {
      const d = grid_row.doc;
      if (frm.doc.parent_warehouse && !d.warehouse) {
        frappe.model.set_value(d.doctype, d.name, "warehouse", frm.doc.parent_warehouse);
      }
    });
  },

  parent_warehouse(frm) {
    frm.doc.locations.forEach(row => {
      frappe.model.set_value(row.doctype, row.name, "warehouse", frm.doc.parent_warehouse);
    });
  }
});
