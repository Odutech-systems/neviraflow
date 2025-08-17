frappe.ui.form.on("Sales Order", {
    onload(frm) {
      apply_territory_tax_logic("Sales Order");
      apply_bag_tonne_logic("Sales Order Item");
      apply_transport_logic("Sales Order");
    }
  });
  