frappe.ui.form.on("Sales Invoice", {
    onload(frm) {
      apply_territory_tax_logic("Sales Invoice");
      apply_bag_tonne_logic("Sales Invoice Item");
      apply_transport_logic("Sales Invoice");
    }
  });
  