frappe.ui.form.on("Delivery Note", {
    onload(frm) {
      apply_territory_tax_logic("Delivery Note");
      apply_bag_tonne_logic("Delivery Note Item");
    }
  });
