frappe.ui.form.on("Stock Entry", {
    onload(frm) {
      apply_bag_tonne_logic("Stock Entry Detail");
    }
  });
  