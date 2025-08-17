frappe.ui.form.on("Quotation", {
    onload(frm) {
      apply_territory_tax_logic("Quotation");
      apply_bag_tonne_logic("Quotation Item");
      apply_transport_logic("Quotation");
    }
  });
  